"""Binary sensor — dostupnost Golemio API pro zastávku."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PidCoordinator
from .sensor import _device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PidCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PidApiSensor(coordinator, entry.entry_id)])


class PidApiSensor(CoordinatorEntity[PidCoordinator], BinarySensorEntity):
    """ON = poslední aktualizace z Golemio API proběhla úspěšně."""

    _attr_has_entity_name = True
    _attr_translation_key = "api"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # Entita musí zůstat dostupná i při výpadku API — jinak by nešlo
    # zobrazit stav "off".
    _attr_available = True

    def __init__(self, coordinator: PidCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_api"
        self._attr_device_info = _device_info(coordinator, entry_id)

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict:
        board = self.coordinator.data
        fetched = board.fetched_at if board else None
        return {
            "last_success": fetched.isoformat() if fetched else None,
        }
