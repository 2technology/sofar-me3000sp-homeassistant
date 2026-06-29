# Installatie — SOFAR ME3000SP Home Assistant

Deze gids is geschreven voor iemand die Home Assistant wel gebruikt, maar niet dagelijks YAML bewerkt.

## 1. Vereisten

### Hardware
- SOFAR ME3000SP in **Passive Mode**
- ESP32
- MAX3485 RS485-module, 3.3V, met DE/RE flow-control
- SMA PV-omvormer met Home Assistant sensor `sensor.sunny_pv_power`
- slimme meter sensors:
  - `sensor.electricity_meter_energieproductie` — export in kW
  - `sensor.electricity_meter_energieverbruik` — import in kW

### Home Assistant add-ons / integraties
- ESPHome add-on of losse ESPHome installatie
- optioneel: HACS + Mushroom Cards voor het dashboard
- optioneel: HACS + card-mod voor extra kleuraccenten

## 2. ESPHome flashen

1. Open ESPHome.
2. Maak een nieuw device of importeer `esphome/sofar-me3000sp-esp32.yaml`.
3. Zorg dat je `secrets.yaml` bevat:

```yaml
wifi_ssid: "JOUW_WIFI"
wifi_password: "JOUW_WACHTWOORD"
api_encryption_key: "GENEREER_IN_ESPHOME"
ota_password: "KIES_EEN_WACHTWOORD"
fallback_ap_password: "KIES_EEN_WACHTWOORD"
```

4. Flash eerst via USB.
5. Daarna kan OTA.

## 3. Home Assistant package installeren

Zet dit in `/config/configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Maak daarna deze map aan als ze nog niet bestaat:

```text
/config/packages/
```

Kopieer dit bestand:

```text
home-assistant/packages/sofar_me3000sp.yaml
```

naar:

```text
/config/packages/sofar_me3000sp.yaml
```

## 4. Home Assistant herstarten

1. Ga naar **Developer Tools → YAML**.
2. Klik **Check configuration**.
3. Als dat groen is: herstart Home Assistant.
4. Controleer daarna of deze entities bestaan:
   - `sensor.sofar_grid_export_power`
   - `sensor.sofar_grid_import_power`
   - `sensor.sofar_net_grid_power`
   - `sensor.sofar_flow_direction`
   - `binary_sensor.sofar_charging_active`

## 5. Dashboard installeren

Voor de mooie versie gebruik je:

```text
home-assistant/dashboards/sofar_me3000sp_wall_panel.yaml
```

Open je dashboard, kies **Edit dashboard → Add card → Manual** en plak de kaartconfig.  
Let op: plak de inhoud onder `wall_panel:` als kaart. Als je in de UI plakt, begin dus bij:

```yaml
type: vertical-stack
cards:
```

## 6. Tuning

Na installatie krijg je helpers zoals:

- `input_number.sofar_export_start_w`
- `input_number.sofar_import_start_w`
- `input_number.sofar_pv_min_w`
- `input_number.sofar_balance_w`
- `input_number.sofar_charge_margin_w`
- `input_number.sofar_discharge_margin_w`
- `input_number.sofar_soc_max_charge`
- `input_number.sofar_soc_min_discharge`

Startwaarden zijn veilig/conservatief. Pas ze pas aan na een paar dagen observatie.
