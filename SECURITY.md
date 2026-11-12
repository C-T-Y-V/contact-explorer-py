# Security Policy

The Contact Explorer engineering team takes software security, data isolation, and user privacy seriously. As an offline-first desktop application handling personal communications data, our primary security commitment is strict local confinement: **zero telemetry, zero cloud synchronisation without explicit user action, and zero third-party dependencies**.

---

## Supported Versions

Only the latest active major and patch releases receive security patches.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

---

## Threat Model & Security Posture

- **Data at Rest:** All contacts, groups, tags, and snapshots reside strictly in a local SQLite database (defaulting to WAL mode with foreign key integrity).
- **Network Surface:**
  - The desktop UI runs 100% offline with zero outbound network calls.
  - The optional REST API server (`serve.py`) binds strictly to loopback (`127.0.0.1`) by default and never listens on external interfaces unless explicitly requested.
- **Input Sanitization:** Contact import routines (CSV, vCard, Vault JSON) validate payloads to prevent injection attacks and directory traversals.

---

## Reporting a Vulnerability

If you discover a security vulnerability within Contact Explorer, please do **NOT** open a public issue. Follow our responsible disclosure process:

1. **Email:** Send your report to `priyanshuctyv@gmail.com` with the subject line `[SECURITY] Contact Explorer Vulnerability Report`.
2. **Details:** Include the following information in your report:
   - Component affected (e.g. SQLite storage, API server, vCard parser).
   - Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
   - Potential impact and threat classification (e.g., local privilege escalation, arbitrary file write via export).
   - Your proposed remediation, if available.
3. **Response Timelines:**
   - **Acknowledgment:** Within 48 hours.
   - **Initial Triage & Assessment:** Within 7 business days.
   - **Remediation & Patch Release:** Within 30 days depending on severity.

We request that you do not publicly disclose the vulnerability until an official patch has been published.
