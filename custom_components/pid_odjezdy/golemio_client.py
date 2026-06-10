"""Klient Golemio API — PID departure boards (v2)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import aiohttp

from .const import API_URL, MINUTES_BEFORE, ROUTE_TYPES

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


class GolemioClient:
    def __init__(self, session: aiohttp.ClientSession, api_token: str) -> None:
        self._session = session
        self._token = api_token

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
        headers = {"X-Access-Token": self._token}

        try:
            async with self._session.get(
                API_URL, params=params, headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise GolemioAuthError(f"HTTP {resp.status} — neplatný token")
                if resp.status == 404:
                    raise GolemioStopNotFound(stop_name)
                if resp.status != 200:
                    body = (await resp.text())[:200]
                    raise GolemioError(f"HTTP {resp.status}: {body}")
                payload = await resp.json()
        except aiohttp.ClientError as err:
            raise GolemioError(f"Chyba spojení: {err}") from err

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
