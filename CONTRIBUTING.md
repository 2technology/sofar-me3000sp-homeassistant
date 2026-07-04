# Contributing

Contributions welcome — bug reports, translations, and PRs alike.

## Ground rules

- **Measured, not guessed.** Claims about inverter or meter behaviour need
  evidence: logs, register dumps, or a reproducible test.
- The automation engine in `__init__.py` is the **single source of truth**.
  Sensors report state from the store; they never re-derive decision logic.
- Every decision path must set an honest `decision_reason` — including the
  edge cases where nothing can be done and why.

## Development

```bash
pip install pytest ruff
ruff check custom_components/    # lint
pytest tests/                    # unit tests (no HA install required)
```

CI runs ruff, pytest, [hassfest](https://developers.home-assistant.io/blog/2020/04/16/hassfest/)
and [HACS validation](https://github.com/hacs/action) on every PR.

## Pull requests

1. One logical change per PR
2. Update `CHANGELOG.md` under an `Unreleased` heading
3. New logic in `quarter.py` or the decision tree needs a unit test with an
   analytically derived expected value (see `tests/test_quarter_tracker.py`)
4. User-facing strings live in `strings.json` + `translations/` (EN + NL)

## Translations

`strings.json` is the source of truth; `translations/en.json` mirrors it.
Additional languages: copy `en.json` to `translations/<code>.json` and translate.
