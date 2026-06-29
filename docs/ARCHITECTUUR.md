# Architectuur

## Principe

De SOFAR ME3000SP wordt behandeld als actuator. Home Assistant beslist op basis van externe, betrouwbare metingen.

```text
Slimme meter export/import ┐
                           ├─ Home Assistant package ── charge/discharge/auto/standby ── ESPHome ── SOFAR
SMA PV power ──────────────┘
```

## Niet gebruikt voor beslissingen
- interne Sofar PV/load metingen
- CT-klem powerflow
- battery_save-logica

## Wel gebruikt
- `sensor.electricity_meter_energieproductie`
- `sensor.electricity_meter_energieverbruik`
- `sensor.sunny_pv_power`
- SOFAR SOC/faults als safety guardrails

## Modi
- `auto`: neutrale baseline
- `charge`: laden met variabel vermogen gebaseerd op netto export
- `discharge`: ontladen met variabel vermogen gebaseerd op netto import
- `standby`: noodstop/alarm
