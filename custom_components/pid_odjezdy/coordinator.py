"""DataUpdateCoordinator pro integraci PID Odjezdy."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CANCELED_SKIP,
    CONF_CANCELED_MODE,
    CONF_DEPARTURES_COUNT,
    CONF_MINUTES_AFTER,
    CONF_PLATFORM_FILTER,
    CONF_ROUTE_FILTER,
    CONF_SCAN_INTERVAL,
    CONF_STOP_NAME,
    DEFAULT_CANCELED_MODE,
    DEFAULT_DEPARTURES_COUNT,
    DEFAULT_MINUTES_AFTER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .golemio_client import BoardData, GolemioClient, GolemioError

_LOGGER = logging.getLogger(__name__)

# Při aktivním filtru linek/nástupiště se stahuje větší okno, aby po
# odfiltrování zbyl plný počet spojů.
FILTER_FETCH_LIMIT = 100


def _split_filter(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


class PidCoordinator(DataUpdateCoordinator[BoardData]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: GolemioClient,
        config: dict,
    ) -> None:
        self.stop_name: str = config[CONF_STOP_NAME]
        self.count: int = config.get(CONF_DEPARTURES_COUNT, DEFAULT_DEPARTURES_COUNT)
        self._minutes_after: int = config.get(CONF_MINUTES_AFTER, DEFAULT_MINUTES_AFTER)
        self._skip_canceled: bool = (
            config.get(CONF_CANCELED_MODE, DEFAULT_CANCELED_MODE) == CANCELED_SKIP
        )
        self._route_filter = _split_filter(config.get(CONF_ROUTE_FILTER))
        self._platform_filter = _split_filter(config.get(CONF_PLATFORM_FILTER))
        self._client = client

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.stop_name}",
            update_interval=timedelta(
                seconds=config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

    async def _async_update_data(self) -> BoardData:
        has_filter = bool(self._route_filter or self._platform_filter)
        limit = FILTER_FETCH_LIMIT if has_filter else self.count
        try:
            board = await self._client.fetch_board(
                self.stop_name,
                limit=limit,
                minutes_after=self._minutes_after,
                skip_canceled=self._skip_canceled,
            )
        except GolemioError as err:
            raise UpdateFailed(str(err)) from err

        departures = board.departures
        if self._route_filter:
            departures = [
                d for d in departures
                if d.route and d.route.lower() in self._route_filter
            ]
        if self._platform_filter:
            departures = [
                d for d in departures
                if d.platform and d.platform.lower() in self._platform_filter
            ]
        board.departures = departures[: self.count]
        return board
