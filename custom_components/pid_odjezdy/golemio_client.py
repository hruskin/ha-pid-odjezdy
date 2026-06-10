"""Klient Golemio API — PID departure boards (v2)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

import aiohttp

from .const import API_URL, MINUTES_BEFORE, ROUTE_TYPES, STOPS_URL

_LOGGER = logging.getLogger(__name__)


class GolemioError(Exception):
    """Obecná chyba komunikace s Golemio API."""


class GolemioAuthError(GolemioError):
    """Neplatný nebo expirovaný API token."""


class GolemioStopNotFound(GolemioError):
    """Zastávka daného názvu v PID neexistuje."""


@dataclass
class Departure:
    route: str | None
    route_type: str | None
    headsign: str | None
    scheduled: datetime | None
    predicted: datetime | None
    delay_min: int
    delay_available: bool
    platform: str | None
    air_conditioned: bool | None
    wheelchair_accessible: bool | None
    canceled: bool
    at_stop: bool
    last_stop: str | None
    train_number: str | None

    @property
    def display(self) -> str:
        """Formát původní tabule: 'HH:MM(+2)'."""
        ts = self.predicted or self.scheduled
        if ts is None:
            return ""
        out = ts.strftime("%H:%M")
        if self.delay_min > 0:
            out += f"(+{self.delay_min})"
        elif self.delay_min < 0:
            out += f"({self.delay_min})"
        return out


@dataclass
class NearbyStop:
    name: str
    distance_m: int


@dataclass
class Infotext:
    text: str
    valid_from: datetime | None
    valid_to: datetime | None


@dataclass
class BoardData:
    stop_name: str | None
    platforms: list[str] = field(default_factory=list)
    departures: list[Departure] = field(default_factory=list)
    infotexts: list[Infotext] = field(default_factory=list)
    fetched_at: datetime | None = None


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        _LOGGER.debug("Nelze rozparsovat timestamp: %r", value)
        return None


def _parse_departure(item: dict[str, Any]) -> Departure:
    route = item.get("route") or {}
    trip = item.get("trip") or {}
    stop = item.get("stop") or {}
    delay = item.get("delay") or {}
    dep_ts = item.get("departure_timestamp") or {}
    last_stop = item.get("last_stop") or {}

    delay_available = bool(delay.get("is_available"))
    delay_min = int(delay.get("minutes") or 0) if delay_available else 0

    raw_type = route.get("type")
    if isinstance(raw_type, int):
        route_type = ROUTE_TYPES.get(raw_type, str(raw_type))
    else:
        route_type = str(raw_type) if raw_type is not None else None

    return Departure(
        route=route.get("short_name"),
        route_type=route_type,
        headsign=trip.get("headsign"),
        scheduled=_parse_ts(dep_ts.get("scheduled")),
        predicted=_parse_ts(dep_ts.get("predicted")),
        delay_min=delay_min,
        delay_available=delay_available,
        platform=stop.get("platform_code"),
        air_conditioned=trip.get("is_air_conditioned"),
        wheelchair_accessible=trip.get("is_wheelchair_accessible"),
        canceled=bool(trip.get("is_canceled")),
        at_stop=bool(trip.get("is_at_stop")),
        last_stop=last_stop.get("name"),
        train_number=trip.get("short_name"),
    )


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Haversine — vzdálenost dvou souřadnic v metrech."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return int(2 * 6371000 * asin(sqrt(a)))


class GolemioClient:
    def __init__(self, session: aiohttp.ClientSession, api_token: str) -> None:
        self._session = session
        self._token = api_token

    async def _get_json(self, url: str, params: dict[str, Any]) -> Any:
        headers = {"X-Access-Token": self._token}
        try:
            async with self._session.get(
                url, params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise GolemioAuthError(f"HTTP {resp.status} — neplatný token")
                if resp.status == 404:
                    raise GolemioStopNotFound(str(params))
                if resp.status != 200:
                    body = (await resp.text())[:200]
                    raise GolemioError(f"HTTP {resp.status}: {body}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise GolemioError(f"Chyba spojení: {err}") from err

    async def find_nearby_stops(
        self, lat: float, lon: float, *, range_m: int, max_results: int
    ) -> list[NearbyStop]:
        """Zastávky PID kolem souřadnic, seřazené podle vzdálenosti.

        Sloupky téže zastávky (nástupiště A/B/…) jsou sloučené pod jedním
        názvem — departureboards stejně bere celou zastávku přes `names`.
        Parametr `range` na straně Golemia vrací HTTP 500, okruh se proto
        ořezává až tady z pole `distance` v odpovědi.
        """
        payload = await self._get_json(
            STOPS_URL,
            {"latlng": f"{lat},{lon}", "limit": 200},
        )
        nearest: dict[str, int] = {}
        for feature in payload.get("features") or []:
            props = feature.get("properties") or {}
            name = props.get("stop_name")
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if not name:
                continue
            dist = props.get("distance")
            if dist is None and len(coords) >= 2:
                dist = _distance_m(lat, lon, coords[1], coords[0])
            if dist is None:
                continue
            dist = int(dist)
            if name not in nearest or dist < nearest[name]:
                nearest[name] = dist
        stops = [NearbyStop(name=n, distance_m=d) for n, d in nearest.items()]
        stops.sort(key=lambda s: s.distance_m)
        in_range = [s for s in stops if s.distance_m <= range_m]
        # Bez zastávky v okruhu (samota, chalupa) nabídni aspoň nejbližší.
        return (in_range or stops)[:max_results]

    async def fetch_board(
        self,
        stop_name: str,
        *,
        limit: int,
        minutes_after: int,
        skip_canceled: bool,
    ) -> BoardData:
        params: dict[str, Any] = {
            "names": stop_name,
            "minutesBefore": MINUTES_BEFORE,
            "minutesAfter": minutes_after,
            "limit": limit,
            "total": limit,
            "offset": 0,
            "includeMetroTrains": "true",
            "airCondition": "true",
            "filter": "none",
            "skip": "canceled" if skip_canceled else "atStop",
            "preferredTimezone": "Europe/Prague",
        }
        payload = await self._get_json(API_URL, params)

        stops = payload.get("stops") or []
        if not stops:
            raise GolemioStopNotFound(stop_name)

        departures = [_parse_departure(d) for d in payload.get("departures") or []]
        infotexts = [
            Infotext(
                text=i.get("text") or "",
                valid_from=_parse_ts(i.get("valid_from")),
                valid_to=_parse_ts(i.get("valid_to")),
            )
            for i in payload.get("infotexts") or []
            if i.get("text")
        ]
        platforms = sorted(
            {s.get("platform_code") for s in stops if s.get("platform_code")}
        )
        return BoardData(
            stop_name=stops[0].get("stop_name") or stop_name,
            platforms=platforms,
            departures=departures,
            infotexts=infotexts,
            fetched_at=datetime.now(timezone.utc),
        )
