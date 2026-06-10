"""Konstanty integrace PID Odjezdy."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "pid_odjezdy"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

API_URL = "https://api.golemio.cz/v2/pid/departureboards"

CONF_API_TOKEN = "api_token"
CONF_STOP_NAME = "stop_name"
CONF_DEPARTURES_COUNT = "departures_count"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MINUTES_AFTER = "minutes_after"
CONF_CANCELED_MODE = "canceled_mode"
CONF_ROUTE_FILTER = "route_filter"
CONF_PLATFORM_FILTER = "platform_filter"

CANCELED_SKIP = "skip"
CANCELED_SHOW = "show"

DEFAULT_DEPARTURES_COUNT = 6
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MINUTES_AFTER = 1440
DEFAULT_CANCELED_MODE = CANCELED_SKIP

MIN_DEPARTURES_COUNT = 1
MAX_DEPARTURES_COUNT = 20
MIN_SCAN_INTERVAL = 20
MAX_SCAN_INTERVAL = 600
MIN_MINUTES_AFTER = 30
MAX_MINUTES_AFTER = 1440

# Odjezdy až 10 minut zpět — zpožděný spoj nezmizí z tabule v okamžiku
# plánovaného odjezdu (stejně jako v původním Node-RED flow).
MINUTES_BEFORE = 10

# GTFS route_type -> typ dopravy
ROUTE_TYPES = {
    0: "tram",
    1: "metro",
    2: "train",
    3: "bus",
    4: "ferry",
    7: "funicular",
    11: "trolleybus",
}
