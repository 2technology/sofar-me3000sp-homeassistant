# Changelog

## v1.1.1 — 2026-06-29

### Toegevoegd
- `services.yaml` voor handmatige mode/rate controle via Developer Tools
- `info.md` voor HACS-beschrijving
- `icon.png` + `logo.png` voor HACS UI

### Opgelost
- Timing-bug: `hass.loop.time()` → `time.monotonic()` voor betrouwbare hysterese
- Async/await: alle `_set_mode`/`_set_number` calls nu proper awaited
- Service deregistration bij unload entry
- Ongeldige imports verwijderd (`asyncio`, `cv`, `vol`, `CONF_NAME`, ongebruikte constants)
- `sensor.py`: gedeelde `_get_float`/`_get_str` helpers (was 6× gedupliceerd)
- `binary_sensor.py`: imports helpers from `sensor.py` (geen duplicatie meer)
- `config_flow.py`: `description_placeholders` verwijderd (horen in translations)
- `hacs.json`: vereiste velden gecorrigeerd

### Toegevoegd
- **HACS custom integration** (`custom_components/sofar_me3000sp/`)
  - Config flow met UI-wizard voor entity-selectie
  - Automatische template sensors (export, import, net, surplus, deficit, house load, PV, flow direction, visual summary)
  - Automatische binary sensors (charging, discharging, exporting, importing, balanced, alarm)
  - Automatische number helpers (drempels voor tuning)
  - Interne automation logica (charge/discharge/auto/standby/force-charge)
  - Nederlands + Engels translations
  - `hacs.json` voor HACS-discovery
- Force-charge bij kritisch lage SOC (< 20%)

## v1.0.0 — 2026-06-29

### Toegevoegd
- Complete drop-in Home Assistant package met template sensors, helpers en automations
- ESPHome configuratie voor ESP32 + MAX3485 RS485-sturing
- Wall-panel dashboard (Mushroom Cards + card-mod)
- Eenvoudig Mushroom dashboard
- Installatiegids voor beginners
- Troubleshooting-gids
- Architectuurdocumentatie
- .gitignore
- secrets.yaml.example

### Verwijderd
- `battery_save` modus (gebruikte onbetrouwbare interne Sofar-metingen)
- `me3000sp_rapid` controller en bijbehorende sensoren (dode code)

### Gewijzigd
- Alle automations gebruiken nu uitsluitend slimme meter + SMA PV als waarheid
- ESPHome web_server standaard uitgecomment (veiligheid)
- Dashboard entity-referenties gecorrigeerd
