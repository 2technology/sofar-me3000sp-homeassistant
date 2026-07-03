# SOFAR ME3000SP Controller

**Slimme batterij-aansturing voor Home Assistant, gebaseerd op externe meetbronnen.**

Deze integratie stuurt een SOFAR ME3000SP inverter via ESPHome (ESP32 + MAX3485 RS485), maar gebruikt **niet** de interne Sofar CT/powerflow-metingen voor beslissingen. In plaats daarvan vertrouwt het op:

- je slimme meter (export/import in kW)
- je PV-omvormer (live opbrengst in W)

De SOFAR wordt behandeld als pure **actuator** — de beslissingen worden in Home Assistant genomen op basis van betrouwbare, externe data.

## Features

- **UI-wizard**: selecteer je entities via een formulier — geen YAML
- **9 template sensors**: export, import, netto, surplus, deficit, huislast, PV, flow direction, visual summary
- **6 binary sensors**: charging, discharging, exporting, importing, balanced, alarm
- **11 tunable drempels**: pas aan via de UI zonder code te wijzigen, inclusief force-charge
- **Interne automation logica**: charge/discharge/auto/standby met hysterese
- **Force charge**: batterij beschermen bij kritisch lage SOC
- **Alarm handling**: automatisch standby bij fault
- **3 services**: handmatige mode/rate controle via Developer Tools
- **NL + EN translations**
- **Mermaid architectuurdiagram** in README en docs

## Vereisten

1. Een SOFAR ME3000SP in **Passive Mode**
2. Een ESP32 met ESPHome firmware (zie `esphome/` map)
3. Home Assistant entities voor:
   - slimme meter export (kW)
   - slimme meter import (kW)
   - PV-opbrengst (W)
4. ESPHome entities voor:
   - mode select
   - charge rate number
   - discharge rate number
   - battery SOC sensor
   - fault messages sensor

## Installatie

### Via HACS
1. HACS → Integrations → Custom repositories → voeg deze repo toe (type: Integration)
2. Download "SOFAR ME3000SP Controller"
3. Herstart Home Assistant
4. Settings → Devices & Services → Add Integration → "SOFAR ME3000SP"

### Handmatig
Kopieer `custom_components/sofar_me3000sp/` naar `/config/custom_components/sofar_me3000sp/`