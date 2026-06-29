# Troubleshooting

## De package laadt niet
Controleer `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Controleer daarna via **Developer Tools → YAML → Check configuration**.

## Dashboard toont custom card errors
Installeer via HACS:
- Mushroom Cards
- optioneel card-mod

## Sensors blijven unavailable
Controleer of deze bronentities bestaan:
- `sensor.electricity_meter_energieproductie`
- `sensor.electricity_meter_energieverbruik`
- `sensor.sunny_pv_power`

## Automations schakelen niet
Controleer:
- `sensor.sofar_me3000sp_sofar_me3000sp_fault_messages` moet `OK` zijn
- SOC moet binnen guardrails vallen
- export/import moet 5 minuten boven drempel blijven

## CT-klemwaarden lijken fout
Dat is verwacht in deze architectuur. De CT/powerflow-waarden van de Sofar worden niet gebruikt voor beslissingen.
