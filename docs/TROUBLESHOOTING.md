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

**Hoe controleer je dat?**
1. Ga naar **Developer Tools → States**.
2. Typ `sofar` in het filterveld.
3. Je zou minstens 15 entities moeten zien.
4. Als je er 0 ziet: check of de package in `/config/packages/sofar_me3000sp.yaml` staat en of `configuration.yaml` de `packages:` regel heeft.

## Automations schakelen niet
Controleer:
- `sensor.sofar_me3000sp_sofar_me3000sp_fault_messages` moet `OK` zijn
- SOC moet binnen guardrails vallen
- export/import moet 5 minuten boven drempel blijven

**Hoe traceer je een automation?**
1. Ga naar **Settings → Automations & Scenes**.
2. Zoek op `sofar`.
3. Klik op een automation → **Traces**.
4. Daar zie je precies waarom een automation wel of niet afging.

## ESPHome kan geen verbinding maken met SOFAR
Controleer in ESPHome logs:
1. Open ESPHome → je device → **Logs**.
2. Zoek naar `Modbus` of `CRC` of `timeout`.
3. Veelvoorkomende oorzaken:
   - SOFAR staat niet in **Passive Mode** (check display-menu)
   - MAX3485 A/B omgewisseld
   - flow_control_pin (GPIO5) niet aangesloten op DE+RE
   - baudrate mismatch (moet 9600 8N1 zijn)

## Modbus CRC errors in ESPHome logs
Dit wijst meestal op:
- MAX3485 A/B omgekeerd
- flow_control_pin niet correct
- te lange of slechte RS485-kabel
- stoorbronnen in de buurt (frequentieregelaars, motoren)

## Batterij laadt/ontlaadt niet ondanks dat automation triggert
Controleer:
1. In **Developer Tools → States**: staat `select.sofar_me3000sp_sofar_me3000sp_mode` op de verwachte waarde?
2. Staat `number.sofar_me3000sp_sofar_me3000sp_charge_rate` > 0?
3. Check ESPHome logs: wordt het `0x42` commando verstuurd?
4. Staat de SOFAR in **Passive Mode**? Zonder Passive Mode worden write-commands genegeerd.

## Mode verandert niet in HA
1. Check of de ESPHome device online is.
2. Check of de entity `select.sofar_me3000sp_sofar_me3000sp_mode` beschikbaar is.
3. Probeer handmatig de mode te wijzigen via **Developer Tools → Services** → `select.select_option`.

## CT-klemwaarden lijken fout
Dat is verwacht in deze architectuur. De CT/powerflow-waarden van de Sofar worden niet gebruikt voor beslissingen.

## Ik heb een andere PV-omvormer (geen SMA)
Pas de entity-naam aan in `sofar_me3000sp.yaml`:
- Zoek `sensor.sunny_pv_power`
- Vervang door jouw PV-power entity (bv. `sensor.growatt_pv_power`)

## Ik heb andere slimme-meter entity-namen
Pas aan in `sofar_me3000sp.yaml`:
- `sensor.electricity_meter_energieproductie` → jouw export-entity
- `sensor.electricity_meter_energieverbruik` → jouw import-entity
