# Aanpassen voor jouw setup

Niet iedereen heeft exact dezelfde slimme meter of PV-omvormer. Hier lees je hoe je de integratie of package aanpast.

## HACS integratie

Als je de HACS custom integration gebruikt, pas je entity-namen aan tijdens de setup-wizard. Daarna kun je de drempels tunen via de number-helpers in de UI.

## YAML package

## Mijn PV-omvormer is geen SMA

Open `sofar_me3000sp.yaml` en vervang:

- `sensor.sunny_pv_power` → jouw PV-power entity

Voorbeelden van veelvoorkomende entity-namen:

| Omvormer | Typische entity-naam |
|---|---|
| SMA | `sensor.sunny_pv_power` |
| Growatt | `sensor.growatt_pv_power` |
| SolarEdge | `sensor.solaredge_pv_power` |
| GoodWe | `sensor.goodwe_pv_power` |
| Enphase | `sensor.envoy_pv_power` |
| Fronius | `sensor.fronius_pv_power` |

## Mijn slimme meter heeft andere entity-namen

Vervang in `sofar_me3000sp.yaml`:

- `sensor.electricity_meter_energieproductie` → jouw export-entity
- `sensor.electricity_meter_energieverbruik` → jouw import-entity

**Let op:** de package verwacht kW-waardes. Als jouw meter W-waardes geeft, pas dan de `* 1000` vermenigvuldiging aan in de template sensors.

## Ik heb geen slimme meter, alleen een P1-poort

Als je een P1-poort hebt via bijvoorbeeld de DSMR-integratie, zijn je entities waarschijnlijk:

- `sensor.dsmr_reading_electricity_currently_delivered` (export in kW)
- `sensor.dsmr_reading_electricity_currently_received` (import in kW)

Vervang de entity-namen in `sofar_me3000sp.yaml` met deze waarden.

## Ik wil andere drempels

De standaard drempels zijn conservatief. Na installatie krijg je number-helpers die je via de UI kunt aanpassen:

- `number.sofar_me3000sp_export_start_w` — wanneer start laden? (default: 400W)
- `number.sofar_me3000sp_import_start_w` — wanneer start ontladen? (default: 300W)
- `number.sofar_me3000sp_pv_min_w` — minimale PV voor laden (default: 700W)
- `number.sofar_me3000sp_balance_w` — wanneer is de flow "in balans"? (default: 150W)
- `number.sofar_me3000sp_charge_margin_w` — marge bij laden (default: 150W)
- `number.sofar_me3000sp_discharge_margin_w` — marge bij ontladen (default: 250W)
- `number.sofar_me3000sp_soc_max_charge` — stop laden boven dit % (default: 95%)
- `number.sofar_me3000sp_soc_min_discharge` — stop ontladen onder dit % (default: 35%)
- `number.sofar_me3000sp_soc_force_charge` — SOC waaronder force-charge start (default: 20%)
- `number.sofar_me3000sp_soc_force_charge_target` — SOC waarop force-charge stopt (default: 50%)
- `number.sofar_me3000sp_force_charge_rate` — vermogen tijdens force-charge (default: 1500W)

Pas deze aan via **Settings → Devices & Services → Entities** of via je dashboard.

## Ik wil 's nachts niet ontladen

Voeg een tijdconditie toe aan de discharge-automation, bijvoorbeeld:

```yaml
condition:
  - condition: time
    after: "07:00:00"
    before: "23:00:00"
```

Of gebruik de sun-integratie:

```yaml
condition:
  - condition: sun
    after: sunrise
    before: sunset
```
