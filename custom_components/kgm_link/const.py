"""Constants for the KGM Link integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "kgm_link"

# --- Region / host ----------------------------------------------------------
# This app (com.kgm.link.turkey) ships only "tr" (prod) + "dev". Other regions
# are separate apps; add one by contributing its host (its server key is fetched).
DEFAULT_REGION = "tr"
BASE_URL_TEMPLATE = "https://{region}-open-api.kgm-link.com"
CONF_REGION = "region"
CONF_PIN = "pin"  # remote-control PIN (needed to wake the car for status/location)

# --- Endpoints (all POST) — confirmed live ----------------------------------
EP_PUBLIC_KEY = "/Common/V1/PublicKey"                      # server RSA key (unauth)
EP_LOGIN = "/Customer/V1/Login"                             # eml / password / cnncScn
EP_REFRESH_TOKEN = "/Customer/V1/RefreshToken"
EP_VEHICLES = "/Customer/V1/Vehicles"                       # -> vehicles[]
EP_VEHICLE_FIX_DETAIL = "/Customer/V1/VehiclesFixDetail"    # static detail {vehlId}
EP_CHANGE_DETAIL = "/Customer/V1/VehiclesChangeDetail"      # CACHED status {vehlId} — no PIN, no wake
EP_STATUS_CMD_EV = "/Customer/V1/VehicleStatusCheckCmdEv"   # wake {vehlId, pin} -> rctlMnId
EP_STATUS_RESULT_EV = "/Customer/V1/VehicleStatusCheckResultEv"  # poll {rctlMnId, vehlId}
EP_LOCATION_CMD = "/Customer/V1/LocationFinderCmd"          # {vehlId, pin, userLat/Lng} -> rctlMnId
EP_LOCATION_RESULT = "/Customer/V1/LocationFinderResult"    # poll {rctlMnId, vehlId}

# --- Login/session field names ----------------------------------------------
F_EML = "eml"
F_PASSWORD = "password"
F_CNNC_SCN = "cnncScn"           # login "connection scene"; constant "1"
F_TOKEN = "token"
F_REFRESH_TOKEN = "refreshToken"
F_USER_ID = "userId"
F_RCTL_MN_ID = "rctlMnId"        # command transaction id (Cmd -> Result)

# --- Vehicle list fields ----------------------------------------------------
F_VEHICLES = "vehicles"
F_VEHL_ID = "vehlId"
F_VIN = "vin"
F_MODEL_NAME = "saleMdlNm"
F_IS_EV = "isEv"
F_NICKNAME = "xrclNm"            # trim/nickname-ish label

# --- EV status fields (shared where possible between cached + wake reads) ---
F_SOC = "btrSoc"                 # battery state of charge (%) — in BOTH reads
F_CHARGING_STAT = "btrChargingStat"
F_CHARGE_TYPE = "btcgType"
F_CHARGE_FULL_H = "btcgCmplTimTim"
F_CHARGE_FULL_M = "btcgCmplTimMinu"
F_CHARGE_80_H = "btr80BtcgTimTim"
F_CHARGE_80_M = "btr80BtcgTimMinu"
# cached (VehiclesChangeDetail) — the free, no-wake read
F_RANGE_CACHED = "trvgPsblDist"        # range remaining
F_ODOMETER_CACHED = "acumTrvgDist"     # odometer
F_UPDATED = "pcktUpdtDtm"              # last packet update time (data freshness)
# wake-only (VehicleStatusCheckResultEv) — door/lock states
F_RANGE_WAKE = "evTrvgDist"
F_KEY_STAT = "keyStat"
F_DOOR_DRV = "drvtDoorStat"
F_RETRY_FLAG = "retryFlag"
# location (LocationFinderResult) — needs a wake
F_LAT = "pcktGpsLae"
F_LON = "pcktGpsLoe"
F_LOC_VALID = "locExYn"

# --- Charging-status enum (app labels; int mapping confirmed: 2 = not charging) ---
# TODO: confirm the "charging" int value from a live charging session (likely 1).
CHARGING_STATES: dict[int, str] = {0: "unknown", 1: "charging", 2: "not_charging"}
CHARGING_ACTIVE = {1}  # int values that mean "actively charging"

# --- Poll behaviour ---------------------------------------------------------
# The regular poll uses VehiclesChangeDetail — the same cached read the app shows
# on open: no PIN, no wake, no 12 V cost — so it can run often. The CmdEv wake
# (fresh door states) and LocationFinder (map) are on-demand only.
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
RESULT_POLL_INTERVAL_S = 4
RESULT_POLL_TIMEOUT_S = 60
