# Changelog

## v2.2.1 — 2026-07-04

Maintenance release: repository best practices, no behaviour changes.

### Fixed
- **Config-flow error texts never resolved in the UI**: translations used a
  top-level `errors`/`reconfigure` structure instead of `config.error` /
  `config.step.reconfigure`. Users saw raw keys instead of messages.
- `translations/en.json` contained Dutch descriptions; now fully English
  (NL preserved in `nl.json`, `strings.json` added as source of truth).
- Deprecated `entry_type="service"` string replaced with `DeviceEntryType.SERVICE`.
- Config flow validation returned untranslatable literal strings; now uses
  error keys.

### Added
- **CI**: hassfest + HACS validation, ruff lint, and pytest on every push/PR
  (`.github/workflows/`).
- **Unit tests** for the quarter tracker with analytically derived expected
  values (`tests/test_quarter_tracker.py`, 8 tests).
- `quarter.py`: tracker extracted into a standalone, HA-free module.
- `CONTRIBUTING.md`, `pyproject.toml` (ruff config), `strings.json`.
- `manifest.json`: `integration_type: hub`.

### Changed
- `services.yaml` and `info.md` (HACS storefront) translated to English and
  updated to the v2.2 feature set.
- Ruff cleanup across the component (unused imports, import order).
- Removed redundant `assets/hardware-wiring-diagram-preview.png` (SVG is the
  single source).

## v2.2.0 — 2026-07-03

### Kritieke fixes
- **NameError gefixt**: `SMOOTHING_WINDOW_SECONDS`, `RATE_UPDATE_MIN_INTERVAL` en `RATE_CHANGE_THRESHOLD_W` werden gebruikt maar niet geïmporteerd in `__init__.py`. Hierdoor crashten de charge/discharge-paden van zelfconsumptie volledig en werd bij peak-shaving de discharge-rate nooit ingesteld.
- **Decision Reason = single source of truth**: de sensor las de store niet maar herimplementeerde de logica (zonder strategie-kennis). Nu rapporteert hij exact wat de automation besliste, met attributen (`strategy`, `active_hold`, `hold_remaining_s`, kwartierdata).
- **Nachtbesparing → standby**: nachtmodus zette `auto`, waarin de SOFAR 's nachts gewoon ontlaadt. Nu `standby` (laden op surplus en force-charge blijven werken).
- **Persistentie na herstart**: strategie (`RestoreEntity`) en alle number-helpers (`RestoreNumber`) overleven nu een HA-herstart.
- **Listener-leak gefixt**: automation-listeners worden opgeruimd bij unload/reload; geen dubbele loops meer.

### Kwartierpiek — capaciteitstarief-correct
- Nieuwe klok-kwartier-tracker (:00/:15/:30/:45, zoals Fluvius meet): tijdgewogen integratie van importvermogen, maandpiek op basis van afgesloten kwartieren, maand-rollover, persistent via `RestoreSensor`.
- **Peak-shaving stuurt nu op het geprojecteerde kwartiergemiddelde** i.p.v. momentaan vermogen: spikes worden genegeerd, sluipende kwartieroverschrijdingen worden wél afgevangen, en de discharge-rate is exact wat nodig is (batterijvriendelijk).
- Eerlijke reden wanneer de batterij op minimum-SOC zit terwijl de projectie boven de drempel ligt.

### Nieuwe entiteiten
- `sensor.sofar_quarter_time_remaining` — tijd tot de kwartiergrens (attribuut: eindtijd, mm:ss)
- `sensor.sofar_quarter_avg_w` — tijdgewogen lopend kwartiergemiddelde
- `sensor.sofar_quarter_projected_w` — projectie bij aanhoudend vermogen
- `sensor.sofar_quarter_budget_w` — hoeveel W je de rest van het kwartier nog mag trekken
- `binary_sensor.sofar_peak_risk` — aan zodra projectie > drempel (notificatie-trigger)

### Overige verbeteringen
- Charge- en discharge-throttle gescheiden (blokkeerden elkaar via één gedeelde timestamp)
- Mode wordt alleen gezet als hij wijzigt (geen Modbus-spam meer bij elke meterupdate)
- Smoothing-window 30 s → 120 s en continu gevuld i.p.v. alleen in het actieve pad
- Hold-countdowns zichtbaar in decision reasons (m:ss)

## v2.1.1 — 2026-07-03

### Gewijzigd
- **Migratie van Forgejo naar GitHub**: alle URLs bijgewerkt naar `https://github.com/2technology/sofar-me3000sp-homeassistant`
- `manifest.json`: codeowners → `@2technology`, documentation + issue_tracker → GitHub
- `LICENSE`: volledige MIT tekst met copyright "Mad Science Lab (2technology)"
- Blueprints `source_url` → GitHub URLs
- `INSTALLATIE.md` → GitHub URLs

## v2.1.0 — 2026-07-03

### 🎯 Rate limiting + smoothing — oplaad/ontlaad stabiliteit

#### Probleem
De charge/discharge rate veranderde elke seconde drastisch (bv. 450→1003→1988→1958→1088W in 5 seconden). Oorzaak: de slimme meter update elke seconde → surplus verandert → integratie stuurt elke keer een nieuwe `number.set_value` naar de ESP32.

#### Oplossing
1. **Moving average smoothing**: surplus en deficit worden uitgemiddeld over de laatste 30 seconden (`SMOOTHING_WINDOW_SECONDS`). De rate wordt berekend op basis van dit gemiddelde, niet op de actuele piekwaarde.
2. **Rate update throttle**: de rate wordt maximaal elke 60 seconden bijgewerkt (`RATE_UPDATE_MIN_INTERVAL`), niet bij elke state change.
3. **Minimum change threshold**: de rate wordt alleen aangepast als het verschil > 200W is (`RATE_CHANGE_THRESHOLD_W`), om micro-aanpassingen te voorkomen.

#### Nieuwe constanten
- `RATE_UPDATE_MIN_INTERVAL = 60` — minimaal 60s tussen rate updates
- `RATE_CHANGE_THRESHOLD_W = 200` — minimaal 200W verschil om rate te wijzigen
- `SMOOTHING_WINDOW_SECONDS = 30` — 30s moving average window

#### Nieuwe helper functies
- `_smooth_value(store, key, value, now)` — moving average over SMOOTHING_WINDOW_SECONDS
- `_should_update_rate(store, rate_key, new_rate, now)` — throttle + minimum change check

#### Toegepast op
- Zelfconsumptie charge (surplus-based)
- Zelfconsumptie discharge (deficit-based)
- Peak-shaving discharge (import-based)

## v2.0.1 — 2026-07-01

### Bugfixes
- **`select.py`**: `async_get_last_state()` bestaat niet op `SelectEntity` → verwijderd, gebruikt `initial_option` default
- **`sensor.py`**: 18 ontbrekende imports voor nieuwe strategy/peak/night constants → alle toegevoegd

## v2.0.0 — 2026-07-01

### 🎯 Nieuw: Strategie-systeem + Control Center

Dit is een grote update die de integratie transformeert van losse drempels naar een gecentraliseerd strategie-systeem.

#### Strategie-kiezer (select entity)
Nieuwe entity: `select.sofar_me3000sp_controller_sofar_strategy` — kies via de UI tussen:

| Strategie | Beschrijving |
|---|---|
| **Zelfconsumptie** | Laad bij PV-surplus, ontlaad bij import > threshold. Default. |
| **Peak-shaving** | Houd import onder piekdrempel. Ontlaad alleen bij pieken. |
| **Nachtbesparing** | Geen discharge 's nachts. Bewaar batterij voor overdag. |
| **Forceer laden** | Laad batterij nu ongeacht omstandigheden. |
| **Forceer ontladen** | Ontlaad batterij nu. |
| **Auto** | SOFAR bepaalt zelf. |

#### Peak-shaving logica
- De batterij ontladt alleen als import > piekdrempel (instelbaar, default 2500W)
- Ontlaad vermogen = import − piekdrempel + marge (precies genoeg om onder drempel te blijven)
- Bij normale verbruik (< drempel) staat de batterij in auto — geen onnodige cycli
- Voorkomt het "ping-pong" patroon van discharge→force-charge→discharge

#### Nachtbesparing logica
- Instelbare uren (default 22:00-06:00)
- 's Nachts: geen discharge, batterij bewaard voor overdag
- Overdag: zelfconsumptie logica actief
- Force-charge bij kritiek lage SOC blijft altijd actief

#### Nieuwe sensors
- `sensor.sofar_me3000sp_controller_sofar_monthly_peak_w` — hoogste 15-min gemiddelde import van de maand
- `sensor.sofar_me3000sp_controller_sofar_strategy_status` — uitgebreide status met strategie + beslissingslogica

#### Nieuwe number helpers
- `number.sofar_me3000sp_controller_sofar_peak_threshold_w` — piekdrempel (default 2500W)
- `number.sofar_me3000sp_controller_sofar_night_start_hour` — start nacht (default 22)
- `number.sofar_me3000sp_controller_sofar_night_end_hour` — eind nacht (default 6)

#### Nieuw platform
- `select.py` — select platform voor strategie-kiezer

#### Control Center dashboard
Nieuw: `home-assistant/dashboards/sofar_me3000sp_control_center.yaml` — een centraal controlepaneel met:
- Strategie-kiezer dropdown
- Live status chips (mode, SOC, batterij, import, PV)
- Peak-shaving tracking (maandelijkse piek vs drempel)
- Beslissingslogica in real-time
- Nachtbesparing instellingen
- Laad/ontlaad sliders
- Dagstatistieken

#### Beslissingslogica verbeterd
- `_run_automation` herschreven met strategie-dispatch
- `decision_reason` wordt nu in de store opgeslagen en door sensors gelezen
- Alarm-check en force-charge blijven altijd actief, ongeacht strategie

## v1.3.1 — 2026-07-01

### Bugfix
- **`NameError: CONF_SOFAR_SOC_ENTITY`** — de decision reason sensor crashte bij opstarten omdat `CONF_SOFAR_SOC_ENTITY` en 16 andere consts niet geïmporteerd waren in `sensor.py`. Alle ontbrekende imports toegevoegd.

## v1.3.0 — 2026-07-01

### Toegevoegd
- **Decision Reason sensor** (`sensor.sofar_me3000sp_controller_sofar_decision_reason`) — een sensor die in mensleesbare tekst uitlegt waarom de huidige mode gekozen is. Bijvoorbeeld: `"Charging: surplus 3241W > 400W, PV 3994W > 700W, SOC 47% < 95% → charge @ 2741W"`
- **Live Decision dashboard card** (`home-assistant/dashboards/sofar_me3000sp_live_decision.yaml`) — een visuele Mushroom + card-mod card die in real-time toont:
  - Actieve mode met kleurgecodeerd icoon (groen=charge, amber=discharge, blauw=export, rood=import, rood=alarm)
  - De decision_reason tekst als ondertitel
  - Live energy flow chips: PV, batterij, import, export, huislast
  - Mode selector + SOC gauge met severity zones
  - Laad/ontlaad rate sliders
  - Beslissingslogica panel met monospace tekst

### Veranderd
- Sensor count: 9 → 10 (decision_reason toegevoegd)

## v1.2.3 — 2026-07-01

### Bugfix
- **`sensor.py` en `binary_sensor.py`**: fault-check was nog steeds case-sensitive (`"OK" ≠ "ok"`). De `fault.lower()` fix uit v1.2.2 was alleen toegepast op `__init__.py`, niet op de sensor en binary sensor platformen. Resultaat: `flow_direction = alarm` en `alarm_active = on` terwijl fault_messages = "OK". Nu alle drie de platformen consistent case-insensitive.

## v1.2.2 — 2026-07-01

### 🔴 Kritieke bugfix — alarm-check case mismatch

- **`STATE_OK` is `"ok"` (kleine letters) in Home Assistant, maar de SOFAR stuurt `"OK"` (hoofdletters).** De alarm-check deed `fault not in (STATE_OK, ...)` → `"OK" not in ("ok", ...)` → **True elke keer**. De integratie dacht permanent dat er een alarm was en zette de mode **continu naar standby**. Dit verklaart de ESP32 log met "Mode → STANDBY" elke seconde.
- **Fix**: alle fault-checks gebruiken nu `fault.lower()` voor case-insensitive vergelijking. Toegepast in `__init__.py`, `sensor.py` en `binary_sensor.py`.

## v1.2.1 — 2026-07-01

### 🔴 Kritieke ESPHome fixes (gevonden via live config analyse)

- **`flow_control_pin` behouden op GPIO4** — de hardware is een MAX3485 met DE+RE op GPIO4. Flow control is correct voor deze module.
- **`me3000sp_rapid` controller verwijderd** — twee controllers op hetzelfde Modbus adres (0x01) met verschillende poll-intervallen (30s/5s) veroorzaken bus collisions. Write-commands raken verloren in de chaos.
- **`on_boot` priority 100 → -100** — priority 100 draait voor de modbus_controller (priority -10) is geïnitialiseerd. Het "set auto mode" command bij boot werd gedropt.
- **`battery_save` mode verwijderd** — deze gebruikte interne Sofar PV/load metingen die onbetrouwbaar zijn. Sturing via externe meter in HA is de correcte architectuur.
- **`send_wait_time` 50ms → 200ms, `command_throttle` 20ms → 100ms** — de SOFAR's Modbus implementatie heeft meer tijd nodig tussen requests. Te agressieve timing veroorzaakt timeouts.
- **Fault messages truncatie** — strings > 250 tekens worden afgekapt met "..." om HA's 255-teken limiet te respecteren.

### Hardware specifiek
- ESPHome config nu expliciet voor **MAX3485 RS485 module met flow control op GPIO4**
- GPIO4 drijft DE+RE (samen) — correcte MAX3485 flow control

## v1.2.0 — 2026-06-30

### Verbeterd
- **Catch-all logica**: als geen charge/discharge/balance/force-charge/alarmsituatie actief is en de inverter staat op standby, wordt deze automatisch naar `auto` gezet. Voorkomt dat de inverter in standby blijft hangen na een eerdere alarm-trigger die al opgelost is.
- Gefundeerd in live observatie: surplus 273 W maar mode bleef op standby omdat geen enkele drempel triggerde.

## v1.1.9 — 2026-06-30

### Bugfix
- **`AttributeError: async_get_last_state`** (11 errors) — `NumberEntity` heeft ook geen `async_get_last_state()`. De restore-poging verwijderd; number helpers gebruiken nu gewoon hun `initial_value` uit `__init__`. Dat is betrouwbaar en voldoende voor tunebare drempels.

## v1.1.8 — 2026-06-30

### 🔴 Kritieke bugfixes (live HA fouten opgelost)

- **`NameError: _INVALID_STATES is not defined`** — 17.563 errors in HA. De `_INVALID_STATES` tuple was per ongeluk verwijderd uit `sensor.py` bij de code-deduplicatie in v1.1.6. Alle sensors en binary sensors crashten bij elke state-change. Nu hersteld.
- **`AttributeError: async_get_last_number_data`** — 33 errors. `NumberEntity` heeft geen `async_get_last_number_data()` methode. Vervangen door `async_get_last_state()` met correcte float-casting.
- **ESPHome fault_messages > 255 tekens** — HA viel terug op "unknown" bij lange fault-strings. ESPHome lambda trunkeert nu naar 250 tekens + "...".

### Getest tegen
- Live HA instantie via WebSocket API
- 10 systeem-logentries geanalyseerd, 17.563+ error-count geteld
- Alle fixes verified tegen HA 2024.x entity API

## v1.1.7 — 2026-06-30

### Toegevoegd
- **Reconfigure flow**: pas entity-mapping aan via Settings → Devices & Services → Configure, zonder integratie te verwijderen
- **6 Blueprint automations**: UI-aanpasbare versies van alle automations:
  - `sofar_baseline_auto.yaml` — auto bij zonsopgang
  - `sofar_charge_on_export.yaml` — laden bij export surplus
  - `sofar_discharge_on_import.yaml` — ontladen bij import deficit
  - `sofar_return_auto_balanced.yaml` — terug naar auto bij balans
  - `sofar_alarm_standby.yaml` — noodstop bij alarm
  - `sofar_force_charge_low_soc.yaml` — force-charge bij kritiek lage SOC
- Translations uitgebreid met reconfigure + error keys (NL + EN)

### Gewijzigd
- `config_flow.py`: schema en validatie gerefactoreerd naar herbruikbare functies
- `hacs.json`: minimum HA versie → 2024.2.0 (reconfigure flow vereist)
- README: Blueprint sectie, reconfigure hint, bestandentabel bijgewerkt

## v1.1.6 — 2026-06-30

### Kritieke bugfixes
- **`entity.py`**: `HomeAssistant` niet geïmporteerd maar gebruikt als type hint → `NameError` at runtime. Oplossing: uses `VERSION` constant from `const.py` i.p.v. `async_get_integration` (syncroon, geen import nodig).
- **`entity.py`**: `async_get_integration` is async maar werd zonder `await` aangeroepen → retourneerde coroutine, niet Integration. Volledig verwijderd.
- **`_get_number_helper`**: negeerde `default` parameter bij ongeldige entity state. Geconsolideerd in `number.py` met correcte fallback.
- **`async_unload_entry`**: verwijderde altijd alle services, ook bij multi-entry. Nu alleen bij laatste entry.

### Best practices
- **`_get_number_helper`** niet meer 3x gedupliceerd — gedefinieerd in `number.py`, geïmporteerd waar nodig.
- **`config_flow.py`**: unique ID check toegevoegd — voorkomt duplicate entries met dezelfde SOFAR mode entity.
- **`force_charge_low_soc`** automation: `mode: single` → `mode: restart` (herstart bij verdere SOC daling).
- **Onnodige imports** verwijderd (`_get_number_entity_id` in `sensor.py` en `__init__.py`).
- **`sw_version`**: komt nu uit `const.VERSION` i.p.v. `async_get_integration` — eenvoudiger, sneller, geen async nodig.

### Visueel
- **SVG hardware schema** volledig opnieuw ontworpen: label backgrounds, branched DE/RE routing, twisted-pair A/B curves, notes-balk.
- **README** hardware aansluitschema nu met SVG + tekst fallback.
- **README** tuning table uitgebreid naar 11 drempels (force-charge toegevoegd).
- **README** "8 tunable drempels" gecorrigeerd naar "11 tunable drempels" op alle plaatsen.

## v1.1.5 — 2026-06-29

### Toegevoegd
- **3 extra tunebare number helpers** voor force-charge:
  - `number.sofar_me3000sp_soc_force_charge` (default 20%)
  - `number.sofar_me3000sp_soc_force_charge_target` (default 50%)
  - `number.sofar_me3000sp_force_charge_rate` (default 1500W)
- Visueel indrukwekkend README ASCII-banner header
- SVG hardware aansluitschema verbeterd: glow, gradients, kleurgecodeerde draden, grid-achtergrond

### Opgelost
- **Kritieke bug in `number.py`**: constructor gebruikte undefined `hass` variabele — zou crash geven bij integratie-lading
- **Kritieke bug in `__init__.py`**: force-charge kon in oneindige timeout-lus blijven hangen; nu robuuste target/timeout/clear logica
- Hardcoded `150W` balance drempel in `sensor.py` en `binary_sensor.py` vervangen door tunebare `number.sofar_me3000sp_balance_w`
- `sensor.py`: `house_load` availability controleert nu ook PV-bron
- Async service handlers hebben geen verkeerde `@callback` decorator meer
- `entity.py`: correct type hint voor `hass` parameter

### Gewijzigd
- `info.md` feature count geüpdatet naar 11 tunebare drempels
- `AANPASSEN.md` documenteert nu ook force-charge helpers
- Translations `en.json` + `nl.json` uitgebreid met nieuwe number entities

## v1.1.4 — 2026-06-29

### Toegevoegd
- SVG hardware aansluitschema voor ESP32 ↔ MAX3485 ↔ SOFAR 485s
- Tekst fallback aansluitschema in `docs/INSTALLATIE.md`
- YAML package: force-charge helpers nu tunebaar via UI (`sofar_soc_force_charge`, `sofar_soc_force_charge_target`, `sofar_force_charge_rate_w`)
- `number.py`: restore previous value via `async_get_last_number_data()`
- `sensor.py` / `binary_sensor.py`: availability afgeleid van bron entities (echte HA best practice)
- `entity.py`: `sw_version` nu dynamisch uit `manifest.json`

### Opgelost
- `_get_device_info(..., hass)` doorgegeven in alle platforms (was gebroken na entity.py introductie)
- `manifest.json`: documentatie-link verwijst nu naar Forgejo
- README badge versie → 1.1.4

## v1.1.3 — 2026-06-29

### Toegevoegd
- Mermaid-architectuurdiagram toegevoegd aan README en `docs/ARCHITECTUUR.md`
- Fysieke opstellingsafbeelding toegevoegd aan README (`assets/sofar-me3000sp-architecture.png`)
- `entity.py` met shared `DeviceInfo` — alle entities gegroepeerd als één apparaat in HA
- Dashboard-disclaimer: dashboards zijn ontworpen voor de HACS custom integration

### Opgelost
- `__init__.py`: listener callbacks nu correct async zonder verkeerde `@callback` decorator
- `number.py`: entity-id mapping nu per config entry opgeslagen (was globaal)
- `_get_number_helper`: accepteert nu ook `0` als legitieme drempelwaarde
- `info.md`: typo "besermen" → "beschermen"
- README badges: versie 1.1.3, HACS Custom (was Default)
- `ARCHITECTUUR.md`: volledig herschreven met Mermaid-diagram en beide integratievormen

## v1.1.2 — 2026-06-29

### Toegevoegd
- `services.yaml` voor handmatige mode/rate controle via Developer Tools
- `info.md` voor HACS-beschrijving
- `icon.png` + `logo.png` voor HACS UI
- Forgejo release tags `v1.1.1` en `v1.1.2`

### Opgelost
- Timing-bug: `hass.loop.time()` → `time.monotonic()` voor betrouwbare hysterese
- Async/await: alle `_set_mode`/`_set_number` calls nu proper awaited
- `_setup_automation` nu async (was sync maar werd awaited)
- Service deregistration bij unload entry
- Ongeldige imports verwijderd (`asyncio`, `cv`, `vol`, `CONF_NAME`, ongebruikte constants)
- `sensor.py`: gedeelde `_get_float`/`_get_str` helpers (was 6× gedupliceerd)
- `binary_sensor.py`: imports helpers from `sensor.py` (geen duplicatie meer)
- `config_flow.py`: `description_placeholders` verwijderd (horen in translations)
- `hacs.json`: vereiste velden gecorrigeerd

## v1.1.0 — 2026-06-29

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
- `.gitignore`
- `secrets.yaml.example`

### Verwijderd
- `battery_save` modus (gebruikte onbetrouwbare interne Sofar-metingen)
- `me3000sp_rapid` controller en bijbehorende sensoren (dode code)

### Gewijzigd
- Alle automations gebruiken nu uitsluitend slimme meter + SMA PV als waarheid
- ESPHome `web_server` standaard uitgecomment (veiligheid)
- Dashboard entity-referenties gecorrigeerd
