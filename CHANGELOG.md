# Changelog

## v1.0.0 — 2026-06-29

### Toegevoegd
- Complete drop-in Home Assistant package met template sensors, helpers en automations
- ESPHome configuratie voor ESP32 + MAX3485 RS485-sturing
- Wall-panel dashboard (Mushroom Cards + card-mod)
- Eenvoudig Mushroom dashboard
- Installatiegids voor beginners
- Troubleshooting-gids
- Architectuurdocumentatie
- Force-charge bij kritisch lage SOC (< 20%)
- .gitignore
- secrets.yaml.example

### Verwijderd
- `battery_save` modus (gebruikte onbetrouwbare interne Sofar-metingen)
- `me3000sp_rapid` controller en bijbehorende sensoren (dode code)

### Gewijzigd
- Alle automations gebruiken nu uitsluitend slimme meter + SMA PV als waarheid
- ESPHome web_server standaard uitgecomment (veiligheid)
- Dashboard entity-referenties gecorrigeerd
