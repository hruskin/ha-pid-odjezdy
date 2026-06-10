"""Senzory — odjezdová tabule (souhrnný senzor) a výluky/infotexty."""
from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PidCoordinator
from .golemio_client import Departure


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PidCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PidBoardSensor(coordinator, entry.entry_id),
            PidInfotextSensor(coordinator, entry.entry_id),
        ]
    )


def _device_info(coordinator: PidCoordinator, entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name=f"Odjezdová tabule {coordinator.stop_name}",
        manufacturer="Golemio / PID",
        model="Departure board",
        configuration_url="https://api.golemio.cz/pid/docs/openapi/",
    )


def _departure_dict(dep: Departure) -> dict:
    now = datetime.now(timezone.utc)
    ts = dep.predicted or dep.scheduled
    minutes = round((ts - now).total_seconds() / 60) if ts else None
    return {
        "route": dep.route,
        "type": dep.route_type,
        "headsign": dep.headsign,
        "scheduled": dep.scheduled.isoformat() if dep.scheduled else None,
        "predicted": dep.predicted.isoformat() if dep.predicted else None,
        "minutes": minutes,
        "delay_min": dep.delay_min,
        "delay_available": dep.delay_available,
        "platform": dep.platform,
        "air_conditioned": dep.air_conditioned,
        "wheelchair_accessible": dep.wheelchair_accessible,
        "canceled": dep.canceled,
        "at_stop": dep.at_stop,
        "last_stop": dep.last_stop,
        "train_number": dep.train_number,
        "display": dep.display,
    }


class PidBoardSensor(CoordinatorEntity[PidCoordinator], SensorEntity):
    """Stav = čas nejbližšího odjezdu, atribut `departures` = celá tabule."""

    _attr_has_entity_name = True
    _attr_translation_key = "board"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bus-clock"

    def __init__(self, coordinator: PidCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_board"
        self._attr_device_info = _device_info(coordinator, entry_id)

    @property
    def native_value(self) -> datetime | None:
        deps = self.coordinator.data.departures if self.coordinator.data else []
        if not deps:
            return None
        first = deps[0]
        return first.predicted or first.scheduled

    @property
    def extra_state_attributes(self) -> dict:
        board = self.coordinator.data
        if not board:
            return {}
        deps = board.departures
        first = deps[0] if deps else None
        return {
            "stop_name": board.stop_name,
            "platforms": board.platforms,
            "departures_count": len(deps),
            "next_route": first.route if first else None,
            "next_headsign": first.headsign if first else None,
            "next_display": first.display if first else None,
            "updated_at": board.fetched_at.isoformat() if board.fetched_at else None,
            "departures": [_departure_dict(d) for d in deps],
        }


class PidInfotextSensor(CoordinatorEntity[PidCoordinator], SensorEntity):
    """Stav = počet aktivních výluk/infotextů pro zastávku."""

    _attr_has_entity_name = True
    _attr_translation_key = "infotexts"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator: PidCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_infotexts"
        self._attr_device_info = _device_info(coordinator, entry_id)

    @property
    def native_value(self) -> int:
        board = self.coordinator.data
        return len(board.infotexts) if board else 0

    @property
    def extra_state_attributes(self) -> dict:
        board = self.coordinator.data
        if not board:
            return {}
        return {
            "infotexts": [
                {
                    "text": i.text,
                    "valid_from": i.valid_from.isoformat() if i.valid_from else None,
                    "valid_to": i.valid_to.isoformat() if i.valid_to else None,
                }
                for i in board.infotexts
            ],
        }
