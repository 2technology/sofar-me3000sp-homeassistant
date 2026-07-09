# Security Policy

## Supported versions

Only the latest released version of the SOFAR ME3000SP Controller integration receives security updates.

| Version | Supported          |
| ------- | ---------------- |
| 2.5.x   | ✅               |
| < 2.5.0 | ❌               |

## Reporting a vulnerability

If you discover a security issue that affects this integration or the ESPHome/Modbus control path:

1. **Do not open a public issue.**
2. Send a private message or email to the repository maintainer with:
   - A clear description of the vulnerability
   - Steps to reproduce
   - Possible impact
   - Suggested fix (optional)
3. Allow reasonable time for investigation and a fix before any public disclosure.

## Security considerations for this integration

- This integration can **write commands to a battery inverter**. Protect your Home Assistant instance accordingly: use strong passwords, keep the host OS patched, and limit network exposure.
- The ESPHome device should be on a trusted local network segment. Do not expose the ESP32 API port or Home Assistant directly to the public internet without additional hardening (VPN, reverse proxy, etc.).
- Always flash the ESPHome firmware over USB or trusted local OTA. Verify OTA passwords are unique and not shared with other devices.
- Secrets (`esphome/secrets.yaml`, HA long-lived access tokens) must never be committed to git. They are ignored by `.gitignore` by default.

## Disclosure policy

- Reporter submits private report
- Maintainers acknowledge within 7 days
- Fix prepared, tested, and released
- Public advisory published with release notes
