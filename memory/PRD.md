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


## v2 change request (2026-06) — India collections
- Exactly 3 voice profiles (en-IN, bn-IN, hi-IN). Each has female/male ElevenLabs voice IDs, a TTS model (turbo_v2_5 / v3 / multilingual_v2) and an STT (deepgram nova-3 en/bn/hi). French/US profiles removed
- Campaign-level agent_name (required); settings default_agent_name prefills it. The old company name and "RevLoop" spoken text are removed
- CSV has 4 columns: phone_number, name, bank_name, state/province. Rows missing phone_number or bank_name are rejected, with per-row errors shown before import
- Intro and closing scripts per language are admin-editable, using {{agent_name}}, {{bank_name}} and {{customer_name}}
- State→language rules are editable (default: West Bengal→Bengali, fallback Hindi) and applied at dial time
- 8 canonical dispositions with editable category, rule and closing line. Unreached calls use a configurable bucket (default "Final Denial Closing"); Call Status is kept separately
- The agent picks the disposition via a Vapi `file_disposition` tool, with analysisPlan structuredData as backup. Claude provides the summary and a fallback classification
- Emotion/tone guidelines plus ElevenLabs stability/style settings
- Export has the 14 spreadsheet columns: Transcript as JSON, Recording as /api/recordings/{attempt_id} (proxy stream)
- The dashboard shows counts for all 8 buckets, per campaign and overall
- On startup, legacy settings and dispositions are migrated

## v2.1 (2026-06) Native voices
- English: ElevenLabs Indian English voices Anika (90ipbRoKi4CpHXvKVtl0) and Raju (pzxut4zZz4GImZNlqQ3H)
- Hindi: ElevenLabs Monika Sogam (1qEiC6qsybMkmnNdVMbK) and Raju (zT03pEAEi0VHKciJODfn), turbo_v2_5, STT deepgram nova-3 hi
- Bengali: Azure bn-IN-TanishaaNeural / bn-IN-BashkarNeural, STT azure bn-IN
- Each profile has a TTS provider setting (11labs or azure). Old placeholder voice IDs are migrated on startup

## Round 2 fixes (2026-10-17)
- The confirmed_close lines (en/hi/bn) no longer promise a representative callback; they restate the purpose of the call instead. A hard prompt rule forbids callback promises outside CALLBACK_CLOSE. Stored templates were migrated
- Name pronunciation: admin overrides (full name or single word, per language) are applied first. Otherwise Claude auto-transliterates the name into Bengali/Devanagari script (cached per contact). Only the spoken name is native script; the written name stays unchanged. Settings has a preview tool
- Disposition code "Final Denial Closing" renamed to FINAL_DENIAL_CLOSING (label kept), with data migrated
- Export checked: 14 columns, Transcript as JSON, working Recording link

- P1: Move recordings to AWS S3
- P1: Secondary RPI check (last name / DOB fragment)
- P1: Scheduled callback slots for confirmed parties; real live-transfer later
- P1: Auth/RBAC for supervisors vs operators
- P2: Per-contact timezone calling windows; auto-retry schedule
- P2: Migrate frontend to TypeScript
