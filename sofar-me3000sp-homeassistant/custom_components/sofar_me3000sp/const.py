"""Constants for the SOFAR ME3000SP Controller integration."""

DOMAIN = "sofar_me3000sp"

VERSION = "2.0.1"

# Config entry keys
CONF_EXPORT_ENTITY = "export_entity"
CONF_IMPORT_ENTITY = "import_entity"
CONF_PV_ENTITY = "pv_entity"
CONF_SOFAR_MODE_ENTITY = "sofar_mode_entity"
CONF_SOFAR_CHARGE_RATE_ENTITY = "sofar_charge_rate_entity"
CONF_SOFAR_DISCHARGE_RATE_ENTITY = "sofar_discharge_rate_entity"
CONF_SOFAR_SOC_ENTITY = "sofar_soc_entity"
CONF_SOFAR_FAULT_ENTITY = "sofar_fault_entity"

# Default thresholds
DEFAULT_EXPORT_START_W = 400
DEFAULT_IMPORT_START_W = 300
DEFAULT_PV_MIN_W = 700
DEFAULT_BALANCE_W = 150
DEFAULT_CHARGE_MARGIN_W = 150
DEFAULT_DISCHARGE_MARGIN_W = 250
DEFAULT_SOC_MAX_CHARGE = 95
DEFAULT_SOC_MIN_DISCHARGE = 35
DEFAULT_SOC_FORCE_CHARGE = 20
DEFAULT_SOC_FORCE_CHARGE_TARGET = 50
DEFAULT_FORCE_CHARGE_RATE = 1500
DEFAULT_MAX_RATE = 3000

# Number helper names for force charge tuning
NUMBER_SOC_FORCE_CHARGE = "sofar_soc_force_charge"
NUMBER_SOC_FORCE_CHARGE_TARGET = "sofar_soc_force_charge_target"
NUMBER_FORCE_CHARGE_RATE = "sofar_force_charge_rate"

# Timing
CHARGE_HOLD_SECONDS = 300  # 5 min
DISCHARGE_HOLD_SECONDS = 300
BALANCE_HOLD_SECONDS = 600  # 10 min
FORCE_CHARGE_TIMEOUT = 14400  # 4 uur

# Automation modes
MODE_AUTO = "auto"
MODE_CHARGE = "charge"
MODE_DISCHARGE = "discharge"
MODE_STANDBY = "standby"

# Sensor names
SENSOR_GRID_EXPORT_POWER = "sofar_grid_export_power"
SENSOR_GRID_IMPORT_POWER = "sofar_grid_import_power"
SENSOR_NET_GRID_POWER = "sofar_net_grid_power"
SENSOR_GRID_SURPLUS_POWER = "sofar_grid_surplus_power"
SENSOR_GRID_DEFICIT_POWER = "sofar_grid_deficit_power"
SENSOR_HOUSE_LOAD_POWER = "sofar_house_load_power"
SENSOR_SMA_PV_POWER = "sofar_sma_pv_power"
SENSOR_FLOW_DIRECTION = "sofar_flow_direction"
SENSOR_VISUAL_SUMMARY = "sofar_visual_summary"
SENSOR_DECISION_REASON = "sofar_decision_reason"

# Binary sensor names
BINARY_CHARGING_ACTIVE = "sofar_charging_active"
BINARY_DISCHARGING_ACTIVE = "sofar_discharging_active"
BINARY_EXPORTING = "sofar_exporting"
BINARY_IMPORTING = "sofar_importing"
BINARY_BALANCED_GRID = "sofar_balanced_grid"
BINARY_ALARM_ACTIVE = "sofar_alarm_active"

# Number helper names
NUMBER_EXPORT_START_W = "sofar_export_start_w"
NUMBER_IMPORT_START_W = "sofar_import_start_w"
NUMBER_PV_MIN_W = "sofar_pv_min_w"
NUMBER_BALANCE_W = "sofar_balance_w"
NUMBER_CHARGE_MARGIN_W = "sofar_charge_margin_w"
NUMBER_DISCHARGE_MARGIN_W = "sofar_discharge_margin_w"
NUMBER_SOC_MAX_CHARGE = "sofar_soc_max_charge"
NUMBER_SOC_MIN_DISCHARGE = "sofar_soc_min_discharge"


# === STRATEGIE SYSTEEM ===

# Strategy options
STRATEGY_SELF_CONSUMPTION = "self_consumption"
STRATEGY_PEAK_SHAVING = "peak_shaving"
STRATEGY_NIGHT_SAVE = "night_save"
STRATEGY_FORCE_CHARGE = "force_charge"
STRATEGY_FORCE_DISCHARGE = "force_discharge"
STRATEGY_AUTO = "auto"

STRATEGY_OPTIONS = [
    STRATEGY_SELF_CONSUMPTION,
    STRATEGY_PEAK_SHAVING,
    STRATEGY_NIGHT_SAVE,
    STRATEGY_FORCE_CHARGE,
    STRATEGY_FORCE_DISCHARGE,
    STRATEGY_AUTO,
]

STRATEGY_LABELS = {
    STRATEGY_SELF_CONSUMPTION: "Zelfconsumptie",
    STRATEGY_PEAK_SHAVING: "Peak-shaving",
    STRATEGY_NIGHT_SAVE: "Nachtbesparing",
    STRATEGY_FORCE_CHARGE: "Forceer laden",
    STRATEGY_FORCE_DISCHARGE: "Forceer ontladen",
    STRATEGY_AUTO: "Auto (SOFAR bepaalt)",
}

# Select entity names
SELECT_STRATEGY = "sofar_strategy"

# Peak-shaving defaults
DEFAULT_PEAK_THRESHOLD_W = 2500
DEFAULT_PEAK_LOOKBACK_MINUTES = 15

# Night save hours
DEFAULT_NIGHT_START_HOUR = 22
DEFAULT_NIGHT_END_HOUR = 6

# Peak tracking sensor names
SENSOR_MONTHLY_PEAK_W = "sofar_monthly_peak_w"
SENSOR_PEAK_STATUS = "sofar_peak_status"
SENSOR_STRATEGY_STATUS = "sofar_strategy_status"
SENSOR_CYCLE_COUNT = "sofar_cycle_count"

# Peak-shaving number helper names
NUMBER_PEAK_THRESHOLD_W = "sofar_peak_threshold_w"
NUMBER_NIGHT_START_HOUR = "sofar_night_start_hour"
NUMBER_NIGHT_END_HOUR = "sofar_night_end_hour"
