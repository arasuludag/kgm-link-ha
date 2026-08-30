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

# --- Remote command endpoints (all POST) ------------------------------------
# Schemas recovered from the app binary's Swift reflection metadata; see
# research/PROTOCOL.md §7. NOTE: these take "vehicleId", NOT the "vehlId" the
# status/detail endpoints use.
EP_REMOTE_DOOR = "/Customer/V1/RemoteDoor"              # {vehicleId, pin, isDoorLock}
EP_ENGINE_START_EV = "/Customer/V1/RemoteEngineStartEv"  # climate/precondition start
EP_ENGINE_STOP_EV = "/Customer/V1/RemoteEngineStopEv"    # {vehicleId, pin}
EP_HVAC_STOP = "/Customer/V1/RemoteHvacStop"             # {vehicleId, pin}
EP_CHARGE_START = "/Customer/V1/ImmediateChargeStartCmd"  # {vehicleId, pin}
EP_CHARGE_STOP = "/Customer/V1/ImmediateChargeCancelCmd"  # {vehicleId, pin}
EP_LAMP_HORN_ON = "/Customer/V1/RemoteLampHornOn"        # {vehicleId, pin, lamp, lampHorn}
EP_LAMP_HORN_OFF = "/Customer/V1/RemoteLampHornOff"      # {vehicleId, pin}

# --- Remote command body fields ---------------------------------------------
# ⚠️ UNVERIFIED except where marked. These came from the CodingKeys *property* names in
# the app binary; the real wire keys are the enum's raw values, which are abbreviated and
# not recoverable statically (research/PROTOCOL.md §7.2). The server rejects a wrong name
# with "10001 <realName> is required" — run research/probe_commands.py to recover them.
# CONFIRMED 2026-08-31: remote commands take the SAME vehlId as the status endpoints.
# (An earlier note here claimed they used "vehicleId" — that was wrong; the server asks
# for vehlId on every one of the eight command endpoints.)
F_PIN = "pin"                    # CONFIRMED on the wire
F_IS_DOOR_LOCK = "doorLock"      # CONFIRMED
F_LAMP = "lamp"                  # CONFIRMED
F_LAMP_HORN = "lampHorn"         # CONFIRMED
# RemoteEngineStartV1Body
F_HVAC_ON = "hvacOn"             # CONFIRMED
F_DEFROST_ON = "dfstOn"          # CONFIRMED
F_REAR_HEAT_ON = "rearWndoHtln"   # CONFIRMED — the server named it in an error
F_AC_TEMPERATURE = "aconTmpt"    # CONFIRMED
F_ENGINE_TIMEOUT = "tot"         # CONFIRMED; minutes, the app caps at 10
# CONFIRMED wire names. Note the irregular abbreviations — drvt/psst/scnd/thrd, and
# "Rght" without the i — none of which could have been guessed from the Swift names.
SEAT_FIELDS: tuple[str, ...] = (
    "drvtSeat", "psstSeat",
    "scndLeftSeat", "scndRghtSeat",
    "thrdLeftSeat", "thrdRghtSeat",
)

# --- Wake-only status fields (VehicleStatusCheckResultEv) --------------------
# Each *Stat has a matching *StatDesc string from the server; prefer the desc when
# present since the int encodings are not documented anywhere.
F_DOOR_LOCK_STATES: dict[str, str] = {   # lock state (locked / unlocked)
    "drvtDoorStat": "door_lock_driver",
    "psstDoorStat": "door_lock_passenger",
    "rearDoorStat": "door_lock_rear",
}
F_OPEN_STATES: dict[str, str] = {        # physically open / closed
    "drvtDoorOpndStat": "door_driver",
    "psstDoorOpndStat": "door_passenger",
    "rearLeftDoorOpndStat": "door_rear_left",
    "rearRghtDoorOpndStat": "door_rear_right",
    "tlgtOpndStat": "tailgate",
    "hoodOpndStat": "hood",
    "srfStat": "sunroof",
}
F_HEADLAMP = "hdeLampStat"

# --- Per-vehicle HVAC bounds (from the vehicle detail payload) ---------------
F_HVAC_TEMP_MIN = "hvactempMin"
F_HVAC_TEMP_MAX = "hvactempMax"
DEFAULT_HVAC_TEMP_MIN = 16.0
DEFAULT_HVAC_TEMP_MAX = 32.0
DEFAULT_HVAC_TEMP = 22.0
HVAC_TEMP_STEP = 0.5

# Climate run time. The app's own picker is 1-10 minutes.
MIN_CLIMATE_DURATION = 1
MAX_CLIMATE_DURATION = 10
DEFAULT_CLIMATE_DURATION = 10

# --- Seat heat/vent levels (SeatLevelValue) ---------------------------------
# THE ONE REMAINING UNVERIFIED ASSUMPTION. The server takes an integer here (it
# accepts 1 and 0 and rejects booleans and strings), but it will not tell us what the
# integers MEAN. SeatLevelValue reads cool_high, cool_mid, cool_low, nope, heat_low,
# heat_mid, heat_high — "nope" sitting in the middle is what a symmetric -3..+3 scale
# looks like, and is why 0 is used for off below.
#
# The alternative reading is that the enum has default 0-based raw values, making
# cool_high=0 and nope=3. If that is right, every climate start sends 0 for untouched
# seats and would blast seat COOLING. So: on the first live climate test, watch the
# seats. If they come on cold with everything set to off, this map is the culprit —
# shift it to 0..6 with off=3.
SEAT_LEVELS: dict[str, int] = {
    "cool_high": -3,
    "cool_medium": -2,
    "cool_low": -1,
    "off": 0,
    "heat_low": 1,
    "heat_medium": 2,
    "heat_high": 3,
}
SEAT_LEVEL_OPTIONS: list[str] = list(SEAT_LEVELS)

# --- Remote command behaviour -----------------------------------------------
# Remote command results are delivered to the app by Firebase push, which HA cannot
# receive (research/PROTOCOL.md §7.3). We set state optimistically and then re-read
# the FREE cached endpoint, which costs the car nothing. Twice, because the car can
# take the best part of a minute to actually act on something like a charge start.
COMMAND_SETTLE_DELAYS_S: tuple[int, ...] = (15, 60)

# Raw btrChargingStat values, for optimistic state after a charge command.
CHARGING_STATE_CHARGING = 1
CHARGING_STATE_NOT_CHARGING = 2
