# BPO RPI Calling Module (RevLoop) — PRD

## Original problem statement
AI outbound calling module for BPO teams that checks Right Party Identification (RPI) against uploaded CSV contact lists, logs call outcomes, and follows the Vapi + ElevenLabs config pattern. Settings: voice gender, language, free-text AI prompt. Four dispositions: RPI_CONFIRMED, WRONG_PARTY, NO_ANSWER_VOICEMAIL, FAILED_NUMBER. Call log UI shows transcript, recording and timestamps. Controls: launch, pause, retry, export. Includes an audit log and hardening (guardrails, CSV validation, webhook idempotency).

## User choices
- Standalone module here (no existing RevLoop codebase in the environment), using the Vapi + ElevenLabs pattern
- Vapi credentials are configured in the admin Settings page (user has keys)
- Claude Sonnet 4.5 (Emergent LLM key) classifies call outcomes
- RPI rule: simple yes/no with conservative classification
- CSV columns: name and phone required; customer_id and language optional

## Architecture
- Backend: FastAPI, split into `server.py` (routes), `call_service.py` (queue worker, Vapi client, simulation, idempotent finalize, missed-webhook poller), `rpi_engine.py` (script and guardrails, CSV validation, classifier) and `models.py` (BaseDocument/PyObjectId)
- Mongo collections: settings, campaigns, contacts, call_attempts, audit_logs
- Frontend: React (JS, CRA template) + shadcn, dark RevLoop admin style. Routes: /rpi/campaigns, /rpi/campaigns/:id, /rpi/settings, /rpi/audit

## Implemented (2026-06)
- Campaign CRUD with per-campaign language, voice gender, voice ID override and prompt
- CSV validate → preview → import: E.164 normalisation, blank names, invalid numbers, extensions, duplicates (in the file and already in the campaign), DNC, landline warning, language aliases
- Queue worker with a concurrency limit, calling-hours enforcement and automatic pause on provider/config errors
- Live Vapi calls use an inline assistant (11labs voice, deepgram transcriber, guardrailed system prompt, webhook with token). Simulation mode is the default (MOCK)
- Webhook (token-auth, idempotent via atomic claim), plus a poller that fetches stale live calls from Vapi
- Classification: provider endedReason overrides, then Claude, with a rules fallback. A confidence threshold downgrades RPI_CONFIRMED to WRONG_PARTY and sets a review flag
- Settings: Vapi API key stored encrypted (Fernet, only last4 returned), phone number ID, voice profiles per language × gender, retries, DNC, calling hours, connection test
- Retry (by disposition or selected contacts; confirmed contacts are excluded), CSV export, audit log

## Backlog
- P1: Secondary RPI check (last name / DOB fragment)
- P1: Scheduled callback slots for confirmed parties; real live-transfer later
- P1: Auth/RBAC for supervisors vs operators
- P2: Per-contact timezone calling windows; auto-retry schedule
- P2: Migrate frontend to TypeScript
