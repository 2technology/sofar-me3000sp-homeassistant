# SOFAR ME3000SP Controller

**Smart battery inverter control for Home Assistant, driven by external truth
sources — not the SOFAR's internal CT clamps.**

Decisions are made in Home Assistant from your **smart meter** (import/export)
and **PV inverter** (live production). The SOFAR ME3000SP is treated as a pure
actuator over ESPHome (ESP32 + MAX3485, Modbus FC 0x42 in Passive Mode).

## Features

- **UI wizard** — pick your entities in a form, reconfigure anytime, no YAML
- **6 strategies** — self-consumption, peak shaving, night save, force charge, force discharge, auto
- **Quarter-peak tracking** for capacity tariffs (e.g. Fluvius): clock-aligned,
  time-weighted quarters; peak shaving controls the *projected* quarter average
- **Honest decision reason** — one sensor explains every decision, with
  machine-readable attributes for dashboards and automations
- **16 sensors · 7 binary sensors · 14 tunable thresholds · 1 strategy selector**
- Settings and strategy **persist across restarts**
- Safety first: alarm → standby, critical SOC → force charge — always
- **3 services** for manual mode/rate control

## Requirements

1. SOFAR ME3000SP in **Passive Mode**
2. ESP32 + MAX3485 flashed with the ESPHome config from the `esphome/` folder
3. Smart meter and PV inverter entities in Home Assistant

Full documentation, wiring diagram, dashboards and blueprints:
[github.com/2technology/sofar-me3000sp-homeassistant](https://github.com/2technology/sofar-me3000sp-homeassistant)
