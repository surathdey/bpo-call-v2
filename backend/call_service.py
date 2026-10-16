"""Outbound call orchestration: Vapi (live) and simulation engine, queue worker, idempotent finalization."""
import asyncio
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from bson import ObjectId
from cryptography.fernet import Fernet

from models import AuditLog, CallAttempt, Campaign, Contact, Settings, now_iso
from rpi_engine import LANGUAGES, build_system_prompt, classify_call, sanitize_name, script_lines

logger = logging.getLogger(__name__)
VAPI_BASE = "https://api.vapi.ai"
fernet = Fernet(os.environ["SETTINGS_MASTER_KEY"].encode())


def encrypt(value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return fernet.decrypt(value.encode()).decode() if value else ""


async def audit(db, event: str, entity_type: str = "", entity_id: str = "", campaign_id=None, **details):
    await db.audit_logs.insert_one(AuditLog(event=event, entity_type=entity_type, entity_id=entity_id,
                                            campaign_id=campaign_id, details=details).to_mongo())


async def get_settings(db) -> Settings:
    doc = await db.settings.find_one({"_id": "global"})
    return Settings.model_validate(doc or {})


def resolve_voice(settings: Settings, campaign: Campaign, language: str) -> str:
    if campaign.voice_id and language == campaign.language:
        return campaign.voice_id
    for vp in settings.voice_profiles:
        if vp.language == language and vp.gender == campaign.voice_gender:
            return vp.voice_id
    return next((vp.voice_id for vp in settings.voice_profiles if vp.gender == campaign.voice_gender), "")


def webhook_url(settings: Settings) -> str:
    base = settings.webhook_base_url.rstrip("/")
    return f"{base}/api/vapi/webhook?token={settings.webhook_token}" if base else ""


def within_calling_hours(settings: Settings) -> bool:
    if not settings.enforce_calling_hours:
        return True
    try:
        hour = datetime.now(ZoneInfo(settings.calling_timezone)).hour
    except Exception:
        hour = datetime.now(timezone.utc).hour
    return settings.calling_hours_start <= hour < settings.calling_hours_end


def build_vapi_payload(settings: Settings, campaign: Campaign, contact: Contact, attempt: CallAttempt) -> dict:
    name = sanitize_name(contact.name)
    lang = LANGUAGES.get(contact.language, LANGUAGES["en-US"])
    prompt = campaign.prompt or settings.default_prompt
    assistant = {
        "name": "RevLoop RPI Verifier",
        "firstMessage": attempt.opening_line,
        "firstMessageMode": "assistant-speaks-first",
        "model": {
            "provider": settings.vapi_model_provider,
            "model": settings.vapi_model,
            "temperature": 0.1,
            "messages": [{"role": "system", "content": build_system_prompt(contact.language, name, settings.company_name, prompt)}],
        },
        "voice": {"provider": "11labs", "voiceId": attempt.voice_id, "model": settings.elevenlabs_model},
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": lang["transcriber"]},
        "endCallFunctionEnabled": True,
        "endCallPhrases": lang["goodbye"],
        "maxDurationSeconds": settings.max_call_duration_seconds,
        "silenceTimeoutSeconds": 15,
        "artifactPlan": {"recordingEnabled": True},
        "serverMessages": ["end-of-call-report", "status-update"],
        "metadata": {"attempt_id": attempt.id, "campaign_id": campaign.id, "contact_id": contact.id},
    }
    hook = webhook_url(settings)
    if hook:
        assistant["server"] = {"url": hook}
    return {"phoneNumberId": settings.phone_number_id, "customer": {"number": contact.phone, "name": name[:40]},
            "assistant": assistant}


def parse_vapi_messages(messages: list) -> list:
    turns = []
    for m in messages or []:
        role = m.get("role")
        text = (m.get("message") or "").strip()
        if role in ("bot", "assistant") and text:
            turns.append({"role": "agent", "text": text, "t": m.get("secondsFromStart")})
        elif role == "user" and text:
            turns.append({"role": "customer", "text": text, "t": m.get("secondsFromStart")})
    return turns


async def finalize_attempt(db, attempt_id: str, *, ended_reason, turns, recording_url=None, duration=None,
                           provider_status="ended", started_at=None, ended_at=None, error=None, source="webhook"):
    """Idempotent: only the first caller wins; repeated callbacks are counted and ignored."""
    claimed = await db.call_attempts.find_one_and_update(
        {"_id": ObjectId(attempt_id), "finalized": False},
        {"$set": {"finalized": True, "provider_status": provider_status, "finalized_at": now_iso()},
         "$inc": {"webhook_events": 1}},
    )
    if not claimed:
        await db.call_attempts.update_one({"_id": ObjectId(attempt_id)}, {"$inc": {"webhook_events": 1}})
        await audit(db, "duplicate_callback_ignored", "call_attempt", attempt_id, source=source)
        return None
    attempt = CallAttempt.from_mongo(claimed)
    settings = await get_settings(db)
    result = await classify_call(turns, attempt.customer_name, attempt.language, ended_reason,
                                 settings.confirm_confidence_threshold)
    ended = ended_at or now_iso()
    update = {"ended_reason": ended_reason, "transcript": turns,
              "transcript_text": "\n".join(f"{t['role'].upper()}: {t['text']}" for t in turns),
              "recording_url": recording_url, "duration_seconds": duration, "error": error,
              "disposition": result["disposition"], "review_required": result["review_required"],
              "classification": result["classification"], "ended_at": ended,
              "started_at": started_at or attempt.started_at}
    await db.call_attempts.update_one({"_id": ObjectId(attempt_id)}, {"$set": update})
    await db.contacts.update_one({"_id": ObjectId(attempt.contact_id), "last_attempt_id": attempt_id}, {"$set": {
        "status": "completed", "disposition": result["disposition"], "review_required": result["review_required"],
        "last_ended_reason": ended_reason, "last_duration": duration, "last_recording_url": recording_url}})
    await audit(db, "call_finalized", "call_attempt", attempt_id, attempt.campaign_id,
                disposition=result["disposition"], ended_reason=ended_reason, source=source,
                classifier=result["classification"]["source"])
    return result


# ---------- Simulation (MOCK provider) ----------
SIM_CUSTOMER = {
    "en-US": {"confirm": "Yes, this is {name}.", "deny": "No, you have the wrong number.", "who": "Who is this?",
              "depends": "Depends why you're calling.", "speaking": "Speaking.", "yes": "Yes.",
              "vm": "Hi, you've reached {first}. I'm not available right now, please leave a message after the tone."},
    "es-US": {"confirm": "Sí, soy {name}.", "deny": "No, número equivocado.", "who": "¿Quién habla?",
              "depends": "Depende de por qué llama.", "speaking": "Diga.", "yes": "Sí.",
              "vm": "Hola, se ha comunicado con {first}. Deje su mensaje después del tono."},
    "fr-CA": {"confirm": "Oui, c'est moi, {name}.", "deny": "Non, c'est un mauvais numéro.", "who": "C'est qui?",
              "depends": "Ça dépend pourquoi vous appelez.", "speaking": "Oui, j'écoute.", "yes": "Oui.",
              "vm": "Bonjour, vous avez joint {first}. Laissez un message après le bip."},
}
SCENARIOS = [("confirm", 34), ("deny", 18), ("ambiguous", 12), ("voicemail", 14), ("no_answer", 10), ("failed", 12)]


def simulate_outcome(contact: Contact, lines: dict) -> dict:
    lang = SIM_CUSTOMER.get(contact.language, SIM_CUSTOMER["en-US"])
    name, first = contact.name, contact.name.split()[0]
    scenario = random.choices([s for s, _ in SCENARIOS], weights=[w for _, w in SCENARIOS])[0]
    if scenario == "failed":
        return {"ended_reason": random.choice(["twilio-failed-to-connect-call", "call.start.error-invalid-number"]),
                "turns": [], "duration": 0.0}
    if scenario == "no_answer":
        return {"ended_reason": "customer-did-not-answer", "turns": [], "duration": 0.0}
    if scenario == "voicemail":
        return {"ended_reason": "voicemail", "turns": [{"role": "customer", "text": lang["vm"].format(first=first), "t": 0.5}],
                "duration": round(random.uniform(6, 12), 1)}
    turns = [{"role": "agent", "text": lines["opening"], "t": 0.4}]
    if scenario == "confirm":
        turns += [{"role": "customer", "text": lang["confirm"].format(name=name), "t": 4.2},
                  {"role": "agent", "text": lines["confirmed"], "t": 5.0}]
    elif scenario == "deny":
        turns += [{"role": "customer", "text": lang["deny"], "t": 4.0}, {"role": "agent", "text": lines["wrong"], "t": 4.9}]
    else:
        amb = random.choice(["who", "depends", "speaking"])
        turns += [{"role": "customer", "text": lang[amb], "t": 3.8}, {"role": "agent", "text": lines["clarify"], "t": 4.6},
                  {"role": "customer", "text": lang["who"], "t": 9.1}, {"role": "agent", "text": lines["wrong"], "t": 9.8}]
    reason = "assistant-ended-call" if scenario != "ambiguous" else "customer-ended-call"
    return {"ended_reason": reason, "turns": turns, "duration": round(turns[-1]["t"] + random.uniform(1, 3), 1)}


async def run_simulated_call(db, attempt: CallAttempt, contact: Contact, lines: dict):
    try:
        await asyncio.sleep(random.uniform(1.5, 3))
        await db.call_attempts.update_one({"_id": ObjectId(attempt.id)},
                                          {"$set": {"provider_status": "in-progress", "started_at": now_iso()}})
        await asyncio.sleep(random.uniform(2, 4))
        outcome = simulate_outcome(contact, lines)
        await finalize_attempt(db, attempt.id, ended_reason=outcome["ended_reason"], turns=outcome["turns"],
                               duration=outcome["duration"], source="simulation")
    except Exception as exc:
        logger.exception("Simulated call failed: %s", exc)


# ---------- Placing calls ----------
async def place_call(db, campaign: Campaign, contact: Contact, settings: Settings):
    name = sanitize_name(contact.name)
    lines = script_lines(contact.language, name, settings.company_name)
    live = settings.call_mode == "live"
    attempt = CallAttempt(campaign_id=campaign.id, contact_id=contact.id, attempt_number=contact.attempts,
                          mode="live" if live else "simulation", customer_name=name, phone=contact.phone,
                          language=contact.language, voice_id=resolve_voice(settings, campaign, contact.language),
                          opening_line=lines["opening"], provider_status="queued")
    res = await db.call_attempts.insert_one(attempt.to_mongo())
    attempt.id = str(res.inserted_id)
    await db.contacts.update_one({"_id": ObjectId(contact.id)},
                                 {"$set": {"last_attempt_id": attempt.id, "last_called_at": now_iso()}})
    if not live:
        asyncio.create_task(run_simulated_call(db, attempt, contact, lines))
        return
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{VAPI_BASE}/call", json=build_vapi_payload(settings, campaign, contact, attempt),
                                     headers={"Authorization": f"Bearer {decrypt(settings.vapi_api_key_encrypted)}"})
    except httpx.HTTPError as exc:
        resp, net_error = None, str(exc)
    if resp is not None and resp.is_success:
        data = resp.json()
        await db.call_attempts.update_one({"_id": ObjectId(attempt.id)}, {"$set": {
            "provider_call_id": data.get("id"), "provider_status": data.get("status", "queued"), "started_at": now_iso()}})
        return
    body = resp.text[:500] if resp is not None else net_error
    status = resp.status_code if resp is not None else 0
    if status == 400 and any(k in body.lower() for k in ("number", "customer", "e.164", "phone")):
        await finalize_attempt(db, attempt.id, ended_reason="call.start.error-invalid-number", turns=[],
                               provider_status="failed", error=body, source="provider_error")
        return
    await db.call_attempts.update_one({"_id": ObjectId(attempt.id)}, {"$set": {
        "finalized": True, "provider_status": "error", "error": f"HTTP {status}: {body}", "finalized_at": now_iso()}})
    await db.contacts.update_one({"_id": ObjectId(contact.id)}, {"$set": {"status": "queued"}, "$inc": {"attempts": -1}})
    await db.campaigns.update_one({"_id": ObjectId(campaign.id)}, {"$set": {"status": "paused", "updated_at": now_iso()}})
    await audit(db, "campaign_auto_paused", "campaign", campaign.id, campaign.id,
                reason="Provider error while creating call", http_status=status, error=body[:200])


async def poll_stale_live_calls(db, settings: Settings):
    """Fallback when webhooks are missed: fetch call state directly from Vapi."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
    stale = await db.call_attempts.find({"mode": "live", "finalized": False, "provider_call_id": {"$ne": None},
                                         "created_at": {"$lt": cutoff}}).to_list(20)
    if not stale or not settings.vapi_api_key_encrypted:
        return
    key = decrypt(settings.vapi_api_key_encrypted)
    async with httpx.AsyncClient(timeout=20) as client:
        for doc in stale:
            attempt = CallAttempt.from_mongo(doc)
            try:
                r = await client.get(f"{VAPI_BASE}/call/{attempt.provider_call_id}", headers={"Authorization": f"Bearer {key}"})
            except httpx.HTTPError:
                continue
            if not r.is_success:
                continue
            call = r.json()
            if call.get("status") != "ended":
                await db.call_attempts.update_one({"_id": ObjectId(attempt.id)}, {"$set": {"provider_status": call.get("status")}})
                continue
            artifact = call.get("artifact") or {}
            await finalize_attempt(db, attempt.id, ended_reason=call.get("endedReason"),
                                   turns=parse_vapi_messages(artifact.get("messages") or call.get("messages")),
                                   recording_url=artifact.get("recordingUrl") or call.get("recordingUrl"),
                                   duration=_duration(call.get("startedAt"), call.get("endedAt")),
                                   started_at=call.get("startedAt"), ended_at=call.get("endedAt"), source="poll")


def _duration(start, end):
    try:
        return round((datetime.fromisoformat(end.replace("Z", "+00:00")) -
                      datetime.fromisoformat(start.replace("Z", "+00:00"))).total_seconds(), 1)
    except Exception:
        return None


async def worker_tick(db):
    settings = await get_settings(db)
    if settings.call_mode == "live":
        await poll_stale_live_calls(db, settings)
    async for cdoc in db.campaigns.find({"status": "running"}):
        campaign = Campaign.from_mongo(cdoc)
        cid = campaign.id
        queued = await db.contacts.count_documents({"campaign_id": cid, "status": "queued"})
        calling = await db.contacts.count_documents({"campaign_id": cid, "status": "calling", "disposition": None})
        if queued == 0 and calling == 0:
            await db.campaigns.update_one({"_id": cdoc["_id"], "status": "running"},
                                          {"$set": {"status": "completed", "updated_at": now_iso()}})
            await audit(db, "campaign_completed", "campaign", cid, cid)
            continue
        if not within_calling_hours(settings):
            continue
        if settings.call_mode == "live" and not (settings.vapi_api_key_encrypted and settings.phone_number_id):
            await db.campaigns.update_one({"_id": cdoc["_id"]}, {"$set": {"status": "paused"}})
            await audit(db, "campaign_auto_paused", "campaign", cid, cid, reason="Vapi credentials missing")
            continue
        active = await db.contacts.count_documents({"status": "calling"})
        for _ in range(max(0, settings.max_concurrent_calls - active)):
            doc = await db.contacts.find_one_and_update(
                {"campaign_id": cid, "status": "queued"},
                {"$set": {"status": "calling", "disposition": None}, "$inc": {"attempts": 1}},
                sort=[("created_at", 1)], return_document=True)
            if not doc:
                break
            await place_call(db, campaign, Contact.from_mongo(doc), settings)
            if (await db.campaigns.find_one({"_id": cdoc["_id"]}))["status"] != "running":
                break
    # contacts finalized go to 'completed'; reconcile any calling contacts whose attempt already finished
    async for c in db.contacts.find({"status": "calling", "last_attempt_id": {"$ne": None}}):
        att = await db.call_attempts.find_one({"_id": ObjectId(c["last_attempt_id"]), "disposition": {"$ne": None}})
        if att:
            await db.contacts.update_one({"_id": c["_id"]}, {"$set": {"status": "completed", "disposition": att["disposition"]}})


async def worker_loop(db):
    while True:
        try:
            await worker_tick(db)
        except Exception as exc:
            logger.exception("Worker tick failed: %s", exc)
        await asyncio.sleep(2)
