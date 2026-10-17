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
from rpi_engine import (build_system_prompt, classify_call, is_latin, resolve_language, sanitize_name,
                        script_lines, transliterate_name)

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


def voice_profile(settings: Settings, language: str):
    return next((vp for vp in settings.voice_profiles if vp.language == language), settings.voice_profiles[0])


def resolve_voice(settings: Settings, campaign: Campaign, language: str) -> str:
    vp = voice_profile(settings, language)
    return vp.male_voice_id if campaign.voice_gender == "male" else vp.female_voice_id


def call_variables(campaign: Campaign, contact: Contact, spoken: str = "") -> dict:
    return {"agent_name": campaign.agent_name, "bank_name": contact.bank_name,
            "customer_name": spoken or sanitize_name(contact.name), "state": contact.state}


async def spoken_name(db, settings: Settings, contact: Contact) -> str:
    """Name as the TTS should say it: admin overrides first, then cached/auto native-script transliteration."""
    name = sanitize_name(contact.name)
    rules = [o for o in settings.pronunciation_overrides if o.language == contact.language]
    full = next((o.spoken for o in rules if o.name.strip().lower() == name.lower()), None)
    if full:
        return full
    words = {o.name.strip().lower(): o.spoken for o in rules}
    result = " ".join(words.get(w.lower(), w) for w in name.split())
    if not settings.auto_transliterate_names or not is_latin(result):
        return result
    cache_key = f"{contact.language}:{result}"
    cached = contact.spoken_names.get(cache_key)
    if cached:
        return cached
    try:
        spoken = await transliterate_name(result, contact.language)
    except Exception as exc:
        logger.warning("Name transliteration failed for %s: %s", contact.id, exc)
        return result
    await db.contacts.update_one({"_id": ObjectId(contact.id)}, {"$set": {f"spoken_names.{cache_key}": spoken}})
    return spoken


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


def voice_config(settings: Settings, vp, voice_id: str) -> dict:
    if vp.tts_provider == "11labs":
        cfg = {"provider": "11labs", "voiceId": voice_id, "model": vp.tts_model,
               "stability": settings.voice_stability, "similarityBoost": 0.75, "style": settings.voice_style}
    else:
        cfg = {"provider": vp.tts_provider, "voiceId": voice_id, "model": vp.tts_model}
    return {k: v for k, v in cfg.items() if v not in ("", None)}


def build_vapi_payload(settings: Settings, campaign: Campaign, contact: Contact, attempt: CallAttempt) -> dict:
    from models import DISPOSITIONS
    variables = call_variables(campaign, contact, attempt.spoken_name)
    vp = voice_profile(settings, contact.language)
    prompt = campaign.prompt or settings.default_prompt
    hook = webhook_url(settings)
    tool = {"type": "function", "async": False,
            "function": {"name": "file_disposition",
                         "description": ("File the final call disposition. Call this only AFTER you have fully spoken "
                                         "the closing line, then end the call."),
                         "parameters": {"type": "object", "required": ["disposition"], "properties": {
                             "disposition": {"type": "string", "enum": DISPOSITIONS},
                             "summary": {"type": "string", "description": "One-line English summary of the call"}}}}}
    if hook:
        tool["server"] = {"url": hook}
    assistant = {
        "name": f"RPI {campaign.agent_name}"[:40],
        "firstMessage": attempt.opening_line,
        "firstMessageMode": "assistant-speaks-first",
        "model": {
            "provider": settings.vapi_model_provider,
            "model": settings.vapi_model,
            "temperature": 0.4,
            "messages": [{"role": "system", "content": build_system_prompt(settings, contact.language, variables, prompt)}],
            "tools": [tool],
        },
        "voice": voice_config(settings, vp, attempt.voice_id),
        "transcriber": {k: v for k, v in {"provider": vp.stt_provider, "model": vp.stt_model,
                                          "language": vp.stt_language}.items() if v},
        "endCallFunctionEnabled": True,
        "maxDurationSeconds": settings.max_call_duration_seconds,
        "silenceTimeoutSeconds": 15,
        "artifactPlan": {"recordingEnabled": True},
        "analysisPlan": {"summaryPlan": {"enabled": True}, "structuredDataPlan": {"enabled": True, "schema": {
            "type": "object", "properties": {"disposition": {"type": "string", "enum": DISPOSITIONS}}}}},
        "serverMessages": ["end-of-call-report", "status-update", "tool-calls"],
        "metadata": {"attempt_id": attempt.id, "campaign_id": campaign.id, "contact_id": contact.id},
    }
    if hook:
        assistant["server"] = {"url": hook}
    return {"phoneNumberId": settings.phone_number_id,
            "customer": {"number": contact.phone, "name": sanitize_name(contact.name)[:40]}, "assistant": assistant}


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
                           provider_status="ended", started_at=None, ended_at=None, error=None, source="webhook",
                           agent_disposition=None, agent_summary=""):
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
    variables = {"agent_name": attempt.agent_name, "bank_name": attempt.bank_name,
                 "customer_name": attempt.customer_name, "state": attempt.state}
    result = await classify_call(settings, turns, variables, attempt.language, ended_reason,
                                 attempt.agent_disposition or agent_disposition, attempt.agent_summary or agent_summary)
    ended = ended_at or now_iso()
    update = {"ended_reason": ended_reason, "transcript": turns,
              "transcript_text": "\n".join(f"{t['role'].upper()}: {t['text']}" for t in turns),
              "recording_url": recording_url, "duration_seconds": duration, "error": error,
              "disposition": result["disposition"], "review_required": result["review_required"],
              "classification": result["classification"], "ended_at": ended, "call_status": result["call_status"],
              "category": result["category"], "summary": result["summary"],
              "started_at": started_at or attempt.started_at}
    await db.call_attempts.update_one({"_id": ObjectId(attempt_id)}, {"$set": update})
    await db.contacts.update_one({"_id": ObjectId(attempt.contact_id), "last_attempt_id": attempt_id}, {"$set": {
        "status": "completed", "disposition": result["disposition"], "review_required": result["review_required"],
        "last_ended_reason": ended_reason, "last_duration": duration, "last_recording_url": recording_url,
        "last_call_status": result["call_status"], "last_category": result["category"],
        "last_summary": result["summary"]}})
    await audit(db, "call_finalized", "call_attempt", attempt_id, attempt.campaign_id,
                disposition=result["disposition"], ended_reason=ended_reason, source=source,
                classifier=result["classification"]["source"])
    return result


# ---------- Simulation (MOCK provider) ----------
SIM_CUSTOMER = {
    "en-IN": {"RPC_CONFIRMED": "Yes, I am {name}. Tell me.", "CPC_CONFIRMED": "No, this is his wife. He is not at home right now.",
              "CALLBACK_REQUESTED": "I'm busy right now, please call me later.", "FINAL_DENIAL": "No, wrong number. I don't know any {first}.",
              "HOSTILE": "Stop calling me, you idiot! This is nonsense.", "DECEASED_CASE": "{first} passed away last month.",
              "DNC_ESCALATION": "Do not call this number again or I will file a complaint.", "ambiguous": "Who is this? Why?",
              "vm": "Hi, you've reached {first}. Please leave a message after the beep."},
    "hi-IN": {"RPC_CONFIRMED": "हाँ, मैं ही {name} हूँ। बोलिए।", "CPC_CONFIRMED": "नहीं, मैं उनकी पत्नी बोल रही हूँ। मेरे पति अभी घर पर नहीं हैं।",
              "CALLBACK_REQUESTED": "अभी मैं व्यस्त हूँ, बाद में कॉल कीजिए।", "FINAL_DENIAL": "गलत नंबर है, मैं किसी {first} को नहीं जानता।",
              "HOSTILE": "बकवास बंद करो, पागल हो क्या? बार-बार फ़ोन करते हो!", "DECEASED_CASE": "{first} जी का पिछले महीने निधन हो गया।",
              "DNC_ESCALATION": "इस नंबर पर फ़ोन मत करना, वरना शिकायत करूँगा।", "ambiguous": "कौन बोल रहा है? क्यों?",
              "vm": "आप {first} के वॉइसमेल पर पहुँचे हैं, बीप के बाद संदेश छोड़ें।"},
    "bn-IN": {"RPC_CONFIRMED": "হ্যাঁ, আমিই {name}। বলুন।", "CPC_CONFIRMED": "না, আমি ওঁর স্ত্রী বলছি। আমার স্বামী এখন বাড়িতে নেই।",
              "CALLBACK_REQUESTED": "আমি এখন ব্যস্ত, পরে ফোন করুন।", "FINAL_DENIAL": "ভুল নম্বর, আমি কোনো {first}-কে চিনি না।",
              "HOSTILE": "বাজে কথা বন্ধ করুন, পাগল নাকি? বারবার ফোন করেন!", "DECEASED_CASE": "{first} গত মাসে মারা গেছেন।",
              "DNC_ESCALATION": "এই নম্বরে আর ফোন করবেন না, নইলে অভিযোগ করব।", "ambiguous": "কে বলছেন? কেন?",
              "vm": "আপনি {first}-এর ভয়েসমেলে পৌঁছেছেন, বিপ শব্দের পর বার্তা রেখে যান।"},
}
SCENARIOS = [("RPC_CONFIRMED", 26), ("CPC_CONFIRMED", 8), ("CALLBACK_REQUESTED", 10), ("FINAL_DENIAL", 12),
             ("ambiguous", 8), ("HOSTILE", 6), ("DECEASED_CASE", 5), ("DNC_ESCALATION", 5),
             ("voicemail", 8), ("no_answer", 6), ("failed", 6)]
CLOSE_FOR = {"RPC_CONFIRMED": "confirmed_close", "CPC_CONFIRMED": "cpc_close", "CALLBACK_REQUESTED": "callback_close",
             "FINAL_DENIAL": "denial_close", "ambiguous": "denial_close", "HOSTILE": "hostile_close",
             "DECEASED_CASE": "deceased_close", "DNC_ESCALATION": "dnc_close"}


def simulate_outcome(contact: Contact, lines: dict) -> dict:
    lang = SIM_CUSTOMER.get(contact.language, SIM_CUSTOMER["hi-IN"])
    name, first = contact.name, contact.name.split()[0]
    scenario = random.choices([s for s, _ in SCENARIOS], weights=[w for _, w in SCENARIOS])[0]
    if scenario == "failed":
        return {"ended_reason": random.choice(["twilio-failed-to-connect-call", "call.start.error-invalid-number"]),
                "turns": [], "duration": 0.0}
    if scenario == "no_answer":
        return {"ended_reason": random.choice(["customer-did-not-answer", "customer-busy"]), "turns": [], "duration": 0.0}
    if scenario == "voicemail":
        return {"ended_reason": "voicemail", "turns": [{"role": "customer", "text": lang["vm"].format(first=first), "t": 0.5}],
                "duration": round(random.uniform(6, 12), 1)}
    turns = [{"role": "agent", "text": lines["opening"], "t": 0.4}]
    if scenario == "ambiguous":
        turns += [{"role": "customer", "text": lang["ambiguous"], "t": 4.0}, {"role": "agent", "text": lines["clarify"], "t": 4.8},
                  {"role": "customer", "text": lang["ambiguous"], "t": 9.1}]
    else:
        turns += [{"role": "customer", "text": lang[scenario].format(name=name, first=first), "t": 4.2}]
    turns.append({"role": "agent", "text": lines[CLOSE_FOR[scenario]], "t": turns[-1]["t"] + 1.0})
    reason = "customer-ended-call" if scenario == "HOSTILE" else "assistant-ended-call"
    return {"ended_reason": reason, "turns": turns, "duration": round(turns[-1]["t"] + random.uniform(2, 4), 1)}


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
    contact.language = resolve_language(contact.state, settings.state_language_rules, settings.fallback_language)
    spoken = await spoken_name(db, settings, contact)
    variables = call_variables(campaign, contact, spoken)
    lines = script_lines(settings, contact.language, variables)
    live = settings.call_mode == "live"
    attempt = CallAttempt(campaign_id=campaign.id, contact_id=contact.id, attempt_number=contact.attempts,
                          mode="live" if live else "simulation", customer_name=sanitize_name(contact.name),
                          spoken_name=spoken,
                          phone=contact.phone, bank_name=contact.bank_name, state=contact.state,
                          agent_name=campaign.agent_name, language=contact.language,
                          voice_id=resolve_voice(settings, campaign, contact.language),
                          opening_line=lines["opening"], provider_status="queued")
    res = await db.call_attempts.insert_one(attempt.to_mongo())
    attempt.id = str(res.inserted_id)
    await db.contacts.update_one({"_id": ObjectId(contact.id)}, {"$set": {
        "last_attempt_id": attempt.id, "last_called_at": now_iso(), "language": contact.language}})
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
            analysis = call.get("analysis") or {}
            await finalize_attempt(db, attempt.id, ended_reason=call.get("endedReason"),
                                   turns=parse_vapi_messages(artifact.get("messages") or call.get("messages")),
                                   recording_url=artifact.get("recordingUrl") or call.get("recordingUrl"),
                                   duration=_duration(call.get("startedAt"), call.get("endedAt")),
                                   started_at=call.get("startedAt"), ended_at=call.get("endedAt"), source="poll",
                                   agent_disposition=(analysis.get("structuredData") or {}).get("disposition"),
                                   agent_summary=analysis.get("summary") or "")


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
