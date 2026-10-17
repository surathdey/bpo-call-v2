import asyncio
import csv
import io
import json
import logging
import os
import secrets
from pathlib import Path
from typing import Optional

import httpx
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (DISPOSITIONS, UNREACHED_STATUSES, AuditLog, CallAttempt, Campaign, CampaignCreate,  # noqa: E402
                    CampaignUpdate, Contact, RetryRequest, Settings, SettingsUpdate, now_iso)
from defaults import LEGACY_DISPOSITION_MAP, SCRIPT_KEYS  # noqa: E402
from rpi_engine import (LANGUAGES, build_system_prompt, normalize_phone, resolve_language, sanitize_prompt,  # noqa: E402
                        script_lines, validate_csv)
import call_service as cs  # noqa: E402

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="RevLoop BPO RPI Calling Module")
api = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(404, "Not found")


async def load_campaign(campaign_id: str) -> Campaign:
    doc = await db.campaigns.find_one({"_id": oid(campaign_id)})
    if not doc:
        raise HTTPException(404, "Campaign not found")
    return Campaign.from_mongo(doc)


def public_settings(s: Settings) -> dict:
    data = s.model_dump(exclude={"vapi_api_key_encrypted", "webhook_token"})
    data["has_vapi_api_key"] = bool(s.vapi_api_key_encrypted)
    data["webhook_url"] = cs.webhook_url(s)
    return data


async def campaign_stats(campaign_id: Optional[str] = None) -> dict:
    match = {"campaign_id": campaign_id} if campaign_id else {}
    stats = {"total": 0, "pending": 0, "queued": 0, "calling": 0, "completed": 0, "review_required": 0,
             **{d: 0 for d in DISPOSITIONS}}
    async for row in db.contacts.aggregate([{"$match": match}, {"$group": {
            "_id": {"s": "$status", "d": "$disposition"}, "n": {"$sum": 1},
            "r": {"$sum": {"$cond": ["$review_required", 1, 0]}}}}]):
        stats["total"] += row["n"]
        stats[row["_id"]["s"]] = stats.get(row["_id"]["s"], 0) + row["n"]
        if row["_id"].get("d"):
            stats[row["_id"]["d"]] = stats.get(row["_id"]["d"], 0) + row["n"]
        stats["review_required"] += row["r"]
    done = sum(stats[d] for d in DISPOSITIONS)
    stats["rpi_rate"] = round(stats["RPC_CONFIRMED"] / done * 100, 1) if done else 0.0
    dur = await db.call_attempts.aggregate([{"$match": {**match, "duration_seconds": {"$gt": 0}}},
                                            {"$group": {"_id": None, "avg": {"$avg": "$duration_seconds"}}}]).to_list(1)
    stats["avg_duration"] = round(dur[0]["avg"], 1) if dur else 0.0
    return stats


# ---------- Meta / settings ----------
@api.get("/")
async def root():
    return {"service": "bpo-rpi", "status": "ok"}


@api.get("/meta")
async def meta():
    return {"dispositions": DISPOSITIONS,
            "languages": [{"code": k, "label": v["label"]} for k, v in LANGUAGES.items()]}


@api.get("/settings")
async def read_settings():
    s = await cs.get_settings(db)
    if not s.webhook_token:
        s.webhook_token = secrets.token_urlsafe(24)
        await db.settings.update_one({"_id": "global"}, {"$set": {"webhook_token": s.webhook_token}}, upsert=True)
    return public_settings(s)


def validate_settings_changes(changes: dict):
    langs = set(LANGUAGES)
    if changes.get("fallback_language") not in (None, *langs):
        raise HTTPException(400, "fallback_language must be one of " + ", ".join(langs))
    if "state_language_rules" in changes:
        seen = set()
        for r in changes["state_language_rules"]:
            r["state"] = r["state"].strip()
            key = r["state"].lower()
            if not key or r["language"] not in langs:
                raise HTTPException(400, f"Invalid state rule: {r}")
            if key in seen:
                raise HTTPException(400, f"Duplicate state rule: {r['state']}")
            seen.add(key)
    if "voice_profiles" in changes and sorted(v["language"] for v in changes["voice_profiles"]) != sorted(langs):
        raise HTTPException(400, "Exactly three voice profiles are required: English, Bengali, Hindi")
    if "dispositions" in changes and sorted(d["code"] for d in changes["dispositions"]) != sorted(DISPOSITIONS):
        raise HTTPException(400, "Disposition codes are canonical; only category, description and closing line can change")
    if "dispositions" in changes and any(d["close"] not in SCRIPT_KEYS for d in changes["dispositions"]):
        raise HTTPException(400, "Invalid closing line key")
    if changes.get("unreached_disposition") not in (None, *DISPOSITIONS):
        raise HTTPException(400, "unreached_disposition must be a canonical disposition")
    if "script_templates" in changes:
        if set(changes["script_templates"]) - langs:
            raise HTTPException(400, "Script templates only for en-IN, bn-IN, hi-IN")
        for lang, lines in changes["script_templates"].items():
            if set(lines) - set(SCRIPT_KEYS):
                raise HTTPException(400, f"Unknown script line in {lang}")
            if "{{agent_name}}" not in lines.get("opening", "{{agent_name}}"):
                raise HTTPException(400, f"{lang} opening must include {{{{agent_name}}}}")


@api.put("/settings")
async def update_settings(body: SettingsUpdate):
    s = await cs.get_settings(db)
    changes = body.model_dump(exclude_none=True)
    key = changes.pop("vapi_api_key", None)
    if changes.get("call_mode") not in (None, "simulation", "live"):
        raise HTTPException(400, "call_mode must be 'simulation' or 'live'")
    if "dnc_numbers" in changes:
        region = changes.get("default_region") or s.default_region
        changes["dnc_numbers"] = sorted({normalize_phone(n, region)[0] or n.strip()
                                         for n in changes["dnc_numbers"] if n.strip()})
    validate_settings_changes(changes)
    current = s.model_dump()
    changes = {k: v for k, v in changes.items() if current.get(k) != v}
    if key:
        changes["vapi_api_key_encrypted"] = cs.encrypt(key.strip())
        changes["vapi_api_key_last4"] = key.strip()[-4:]
    final = s.model_copy(update=changes)
    if final.call_mode == "live" and not (final.vapi_api_key_encrypted and final.phone_number_id):
        raise HTTPException(400, "Live mode requires a Vapi API key and Phone Number ID")
    if not final.webhook_token:
        changes["webhook_token"] = secrets.token_urlsafe(24)
    changes["updated_at"] = now_iso()
    await db.settings.update_one({"_id": "global"}, {"$set": changes}, upsert=True)
    await cs.audit(db, "settings_updated", "settings", "global",
                   fields=sorted(k for k in changes if k not in ("updated_at", "vapi_api_key_encrypted")),
                   api_key_rotated=bool(key))
    return public_settings(await cs.get_settings(db))


@api.post("/settings/rotate-webhook-token")
async def rotate_webhook_token():
    await db.settings.update_one({"_id": "global"}, {"$set": {"webhook_token": secrets.token_urlsafe(24)}}, upsert=True)
    await cs.audit(db, "webhook_token_rotated", "settings", "global")
    return public_settings(await cs.get_settings(db))


@api.post("/settings/test-vapi")
async def test_vapi():
    s = await cs.get_settings(db)
    if not (s.vapi_api_key_encrypted and s.phone_number_id):
        raise HTTPException(400, "Save a Vapi API key and Phone Number ID first")
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{cs.VAPI_BASE}/phone-number/{s.phone_number_id}",
                            headers={"Authorization": f"Bearer {cs.decrypt(s.vapi_api_key_encrypted)}"})
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Could not reach Vapi: {exc}")
    ok = r.is_success
    data = r.json() if ok else {}
    await cs.audit(db, "vapi_connection_test", "settings", "global", success=ok, http_status=r.status_code)
    return {"ok": ok, "http_status": r.status_code, "number": data.get("number"), "provider": data.get("provider"),
            "message": "Connected" if ok else r.text[:300]}


@api.get("/dashboard")
async def dashboard():
    s = await cs.get_settings(db)
    return {"stats": await campaign_stats(), "call_mode": s.call_mode,
            "campaigns": await db.campaigns.count_documents({}),
            "running": await db.campaigns.count_documents({"status": "running"}),
            "vapi_configured": bool(s.vapi_api_key_encrypted and s.phone_number_id)}


# ---------- Campaigns ----------
@api.get("/campaigns")
async def list_campaigns():
    docs = await db.campaigns.find().sort("created_at", -1).to_list(500)
    out = []
    for d in docs:
        c = Campaign.from_mongo(d)
        out.append({**c.model_dump(), "stats": await campaign_stats(c.id)})
    return out


@api.post("/campaigns")
async def create_campaign(body: CampaignCreate):
    s = await cs.get_settings(db)
    if body.voice_gender not in (None, "male", "female"):
        raise HTTPException(400, "voice_gender must be male or female")
    c = Campaign(name=body.name.strip(), description=body.description, agent_name=body.agent_name.strip(),
                 voice_gender=body.voice_gender or s.default_voice_gender,
                 prompt=body.prompt if body.prompt is not None else s.default_prompt)
    res = await db.campaigns.insert_one(c.to_mongo())
    c.id = str(res.inserted_id)
    await cs.audit(db, "campaign_created", "campaign", c.id, c.id, name=c.name, agent_name=c.agent_name)
    return {**c.model_dump(), "stats": await campaign_stats(c.id)}


@api.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    c = await load_campaign(campaign_id)
    s = await cs.get_settings(db)
    _, flags = sanitize_prompt(c.prompt)
    variables = {"agent_name": c.agent_name or "{{agent_name}}", "bank_name": "{bank_name}", "customer_name": "{customer_name}"}
    scripts = {lang: {**script_lines(s, lang, variables), "voice_id": cs.resolve_voice(s, c, lang),
                      "label": LANGUAGES[lang]["label"]} for lang in LANGUAGES}
    return {**c.model_dump(), "stats": await campaign_stats(c.id), "prompt_flags": flags, "scripts": scripts,
            "state_rules": [r.model_dump() for r in s.state_language_rules], "fallback_language": s.fallback_language,
            "call_mode": s.call_mode}


@api.patch("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, body: CampaignUpdate):
    c = await load_campaign(campaign_id)
    changes = body.model_dump(exclude_none=True)
    if changes.get("voice_gender") not in (None, "male", "female"):
        raise HTTPException(400, "voice_gender must be male or female")
    if "agent_name" in changes:
        changes["agent_name"] = changes["agent_name"].strip()
    changes["updated_at"] = now_iso()
    await db.campaigns.update_one({"_id": oid(c.id)}, {"$set": changes})
    await cs.audit(db, "campaign_updated", "campaign", c.id, c.id, fields=sorted(changes))
    return await get_campaign(campaign_id)


@api.get("/campaigns/{campaign_id}/prompt-preview")
async def prompt_preview(campaign_id: str, name: str = "Ramesh Kumar", bank: str = "Sample Bank", state: str = ""):
    c = await load_campaign(campaign_id)
    s = await cs.get_settings(db)
    _, flags = sanitize_prompt(c.prompt)
    lang = resolve_language(state, s.state_language_rules, s.fallback_language)
    variables = {"agent_name": c.agent_name, "bank_name": bank, "customer_name": name, "state": state}
    return {"language": lang, "system_prompt": build_system_prompt(s, lang, variables, c.prompt), "flags": flags}


async def _validation_report(campaign: Campaign, file: UploadFile) -> dict:
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV exceeds 5 MB")
    s = await cs.get_settings(db)
    existing = {d["phone"] for d in await db.contacts.find({"campaign_id": campaign.id}, {"phone": 1}).to_list(None)}
    return validate_csv(content, s.default_region, s, existing, set(s.dnc_numbers))


@api.post("/campaigns/{campaign_id}/contacts/validate")
async def validate_contacts(campaign_id: str, file: UploadFile = File(...)):
    c = await load_campaign(campaign_id)
    report = await _validation_report(c, file)
    return {**report, "valid_count": len(report["valid"]), "invalid_count": len(report["invalid"]),
            "valid": report["valid"][:200], "invalid": report["invalid"][:500]}


@api.post("/campaigns/{campaign_id}/contacts/import")
async def import_contacts(campaign_id: str, file: UploadFile = File(...)):
    c = await load_campaign(campaign_id)
    report = await _validation_report(c, file)
    if report["header_errors"] and not report["valid"]:
        raise HTTPException(400, "; ".join(report["header_errors"]))
    docs = [Contact(campaign_id=c.id, name=r["name"], phone=r["phone"], raw_phone=r["raw_phone"],
                    bank_name=r["bank_name"], state=r["state"], language=r["language"], warnings=r["warnings"],
                    status="queued" if c.status == "running" else "pending").to_mongo() for r in report["valid"]]
    if docs:
        await db.contacts.insert_many(docs)
    await cs.audit(db, "contacts_imported", "campaign", c.id, c.id, filename=file.filename,
                   imported=len(docs), rejected=len(report["invalid"]))
    return {"imported": len(docs), "rejected": len(report["invalid"]), "stats": await campaign_stats(c.id)}


@api.get("/campaigns/{campaign_id}/contacts")
async def list_contacts(campaign_id: str, disposition: Optional[str] = None, status: Optional[str] = None,
                        q: Optional[str] = None, review: Optional[bool] = None, language: Optional[str] = None,
                        limit: int = Query(500, le=2000)):
    query = {"campaign_id": campaign_id}
    if disposition:
        query["disposition"] = None if disposition == "NONE" else disposition
    if status:
        query["status"] = status
    if language:
        query["language"] = language
    if review is not None:
        query["review_required"] = review
    if q:
        import re as _re
        rx = {"$regex": _re.escape(q), "$options": "i"}
        query["$or"] = [{"name": rx}, {"phone": rx}, {"bank_name": rx}, {"state": rx}]
    docs = await db.contacts.find(query).sort("created_at", 1).to_list(limit)
    return [Contact.from_mongo(d).model_dump() for d in docs]


@api.post("/campaigns/{campaign_id}/launch")
async def launch_campaign(campaign_id: str):
    c = await load_campaign(campaign_id)
    s = await cs.get_settings(db)
    if s.call_mode == "live" and not (s.vapi_api_key_encrypted and s.phone_number_id):
        raise HTTPException(400, "Vapi is not configured. Add credentials in Settings or switch to simulation mode.")
    if not c.agent_name.strip():
        raise HTTPException(400, "Set the campaign agent name (Voice & script) before launching.")
    res = await db.contacts.update_many({"campaign_id": c.id, "status": "pending"}, {"$set": {"status": "queued"}})
    queued = await db.contacts.count_documents({"campaign_id": c.id, "status": "queued"})
    if queued == 0:
        raise HTTPException(400, "No contacts to call. Upload a CSV or retry completed contacts.")
    await db.campaigns.update_one({"_id": oid(c.id)}, {"$set": {"status": "running", "updated_at": now_iso(),
                                                               "launched_at": c.launched_at or now_iso()}})
    await cs.audit(db, "campaign_launched", "campaign", c.id, c.id, queued=queued, newly_queued=res.modified_count,
                   mode=s.call_mode)
    return await get_campaign(campaign_id)


@api.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    c = await load_campaign(campaign_id)
    if c.status != "running":
        raise HTTPException(400, "Campaign is not running")
    await db.campaigns.update_one({"_id": oid(c.id)}, {"$set": {"status": "paused", "updated_at": now_iso()}})
    await cs.audit(db, "campaign_paused", "campaign", c.id, c.id)
    return await get_campaign(campaign_id)


@api.post("/campaigns/{campaign_id}/retry")
async def retry_contacts(campaign_id: str, body: RetryRequest):
    c = await load_campaign(campaign_id)
    s = await cs.get_settings(db)
    query = {"campaign_id": c.id, "status": "completed"}
    if body.contact_ids:
        query["_id"] = {"$in": [oid(i) for i in body.contact_ids]}
        query["disposition"] = {"$ne": "RPC_CONFIRMED"}
    elif body.dispositions:
        query["disposition"] = {"$in": [d for d in body.dispositions if d in DISPOSITIONS]}
    else:
        query["last_call_status"] = {"$in": [st for st in body.call_statuses if st in UNREACHED_STATUSES]}
    if not body.ignore_retry_limit:
        query["attempts"] = {"$lt": s.max_retries + 1}
    skipped = await db.contacts.count_documents({**{k: v for k, v in query.items() if k != "attempts"}}) - \
        await db.contacts.count_documents(query)
    res = await db.contacts.update_many(query, {"$set": {"status": "queued", "disposition": None, "review_required": False}})
    if res.modified_count and c.status in ("running", "completed"):
        await db.campaigns.update_one({"_id": oid(c.id)}, {"$set": {"status": "running", "updated_at": now_iso()}})
    await cs.audit(db, "contacts_retried", "campaign", c.id, c.id, requeued=res.modified_count,
                   skipped_retry_limit=skipped, dispositions=body.dispositions or body.call_statuses)
    return {"requeued": res.modified_count, "skipped_retry_limit": skipped}


EXPORT_COLUMNS = ["phone_number", "callee_name", "bank_name", "state", "Call ID", "Start Time", "End Time", "Duration",
                  "Call Status", "Disposition", "Category", "Summary", "Transcript", "Recording"]


def public_base(s: Settings, request: Request) -> str:
    return (s.webhook_base_url or os.environ.get("PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")


@api.get("/campaigns/{campaign_id}/export")
async def export_contacts(campaign_id: str, request: Request, disposition: Optional[str] = None):
    c = await load_campaign(campaign_id)
    s = await cs.get_settings(db)
    base = public_base(s, request)
    query = {"campaign_id": c.id}
    if disposition:
        query["disposition"] = disposition
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPORT_COLUMNS)
    async for d in db.contacts.find(query).sort("created_at", 1):
        ct = Contact.from_mongo(d)
        att = CallAttempt.from_mongo(await db.call_attempts.find_one({"_id": oid(ct.last_attempt_id)})) \
            if ct.last_attempt_id else None
        if not att:
            w.writerow([ct.phone, ct.name, ct.bank_name, ct.state] + [""] * 4 + [ct.status, "", "", "", "", ""])
            continue
        transcript = json.dumps([{"role": t.get("role"), "text": t.get("text"), "t": t.get("t")} for t in att.transcript],
                                ensure_ascii=False)
        w.writerow([ct.phone, ct.name, ct.bank_name, ct.state, att.provider_call_id or att.id,
                    att.started_at or att.created_at, att.ended_at or "", att.duration_seconds or 0,
                    att.call_status or att.provider_status, att.disposition or "", att.category or "", att.summary,
                    transcript, f"{base}/api/recordings/{att.id}" if att.recording_url else ""])
    await cs.audit(db, "campaign_exported", "campaign", c.id, c.id, disposition=disposition or "ALL")
    fname = f"rpi_{c.name.replace(' ', '_')[:40]}_{(disposition or 'all').replace(' ', '_')}.csv"
    return StreamingResponse(iter(["\ufeff" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@api.get("/recordings/{attempt_id}")
async def get_recording(attempt_id: str):
    doc = await db.call_attempts.find_one({"_id": oid(attempt_id)}, {"recording_url": 1})
    if not doc or not doc.get("recording_url"):
        raise HTTPException(404, "Recording not available")
    client_http = httpx.AsyncClient(timeout=60, follow_redirects=True)
    upstream = await client_http.send(client_http.build_request("GET", doc["recording_url"]), stream=True)
    if not upstream.is_success:
        await upstream.aclose()
        await client_http.aclose()
        raise HTTPException(502, "Recording provider unavailable")

    async def body():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client_http.aclose()
    return StreamingResponse(body(), media_type=upstream.headers.get("content-type", "audio/wav"),
                             headers={"Content-Disposition": f'inline; filename="recording_{attempt_id}.wav"'})


@api.get("/contacts/{contact_id}")
async def get_contact(contact_id: str):
    doc = await db.contacts.find_one({"_id": oid(contact_id)})
    if not doc:
        raise HTTPException(404, "Contact not found")
    attempts = await db.call_attempts.find({"contact_id": contact_id}).sort("created_at", -1).to_list(50)
    return {"contact": Contact.from_mongo(doc).model_dump(),
            "attempts": [CallAttempt.from_mongo(a).model_dump() for a in attempts]}


@api.get("/campaigns/{campaign_id}/calls")
async def list_calls(campaign_id: str, limit: int = Query(200, le=1000)):
    docs = await db.call_attempts.find({"campaign_id": campaign_id}, {"transcript": 0}).sort("created_at", -1).to_list(limit)
    return [CallAttempt.from_mongo(a).model_dump() for a in docs]


# ---------- Vapi webhook ----------
@api.post("/vapi/webhook")
async def vapi_webhook(request: Request, token: Optional[str] = None):
    s = await cs.get_settings(db)
    supplied = token or request.headers.get("x-vapi-secret", "")
    if not s.webhook_token or not secrets.compare_digest(supplied, s.webhook_token):
        raise HTTPException(401, "Invalid webhook token")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    msg = body.get("message") or {}
    call = msg.get("call") or {}
    call_id = call.get("id")
    meta_attempt = ((call.get("assistant") or {}).get("metadata") or {}).get("attempt_id")
    query = {"provider_call_id": call_id} if call_id else None
    doc = await db.call_attempts.find_one(query) if query else None
    if not doc and meta_attempt and ObjectId.is_valid(meta_attempt):
        doc = await db.call_attempts.find_one({"_id": ObjectId(meta_attempt)})
    if not doc:
        logger.warning("Webhook for unknown call %s", call_id)
        return {"ok": True, "ignored": "unknown call"}
    attempt_id = str(doc["_id"])
    mtype = msg.get("type")
    if mtype == "tool-calls":
        results = []
        for tc in msg.get("toolCallList") or msg.get("toolCalls") or []:
            fn = tc.get("function") or {}
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if fn.get("name") == "file_disposition" and args.get("disposition") in DISPOSITIONS:
                await db.call_attempts.update_one({"_id": doc["_id"], "finalized": False}, {"$set": {
                    "agent_disposition": args["disposition"], "agent_summary": str(args.get("summary", ""))[:600]}})
                await cs.audit(db, "agent_disposition_filed", "call_attempt", attempt_id, doc["campaign_id"],
                               disposition=args["disposition"])
                results.append({"toolCallId": tc.get("id"), "result": "Disposition recorded. Say the closing line and end the call."})
            else:
                results.append({"toolCallId": tc.get("id"), "result": "Invalid disposition; choose one from the list."})
        return {"results": results}
    if mtype == "status-update":
        if not doc.get("finalized"):
            await db.call_attempts.update_one({"_id": doc["_id"], "finalized": False},
                                              {"$set": {"provider_status": msg.get("status")}})
        return {"ok": True}
    if mtype != "end-of-call-report":
        return {"ok": True}
    artifact = msg.get("artifact") or {}
    rec = artifact.get("recording") or {}
    recording = (rec.get("stereoUrl") or rec.get("monoUrl") or rec.get("url") if isinstance(rec, dict) else None) \
        or artifact.get("recordingUrl") or msg.get("recordingUrl")
    turns = cs.parse_vapi_messages(artifact.get("messages") or msg.get("messages") or [])
    if not turns and (artifact.get("transcript") or msg.get("transcript")):
        raw = artifact.get("transcript") or msg.get("transcript")
        for line in raw.splitlines():
            role, _, text = line.partition(":")
            if text.strip():
                turns.append({"role": "agent" if role.strip().upper() in ("AI", "BOT", "ASSISTANT") else "customer",
                              "text": text.strip()})
    duration = msg.get("durationSeconds") or cs._duration(msg.get("startedAt") or call.get("startedAt"),
                                                           msg.get("endedAt") or call.get("endedAt") or "")
    analysis = msg.get("analysis") or {}
    await cs.finalize_attempt(db, attempt_id, ended_reason=msg.get("endedReason"), turns=turns,
                              recording_url=recording, duration=duration, started_at=msg.get("startedAt"),
                              ended_at=msg.get("endedAt"), source="webhook",
                              agent_disposition=(analysis.get("structuredData") or {}).get("disposition"),
                              agent_summary=analysis.get("summary") or "")
    return {"ok": True}


# ---------- Audit ----------
@api.get("/audit")
async def audit_logs(event: Optional[str] = None, campaign_id: Optional[str] = None, limit: int = Query(300, le=2000)):
    query = {}
    if event:
        query["event"] = event
    if campaign_id:
        query["campaign_id"] = campaign_id
    docs = await db.audit_logs.find(query).sort("created_at", -1).to_list(limit)
    return [AuditLog.from_mongo(d).model_dump() for d in docs]


app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


async def migrate_legacy():
    """One-time upgrade of v1 data (US/FR languages, 4 RPI dispositions) to the v2 configuration."""
    doc = await db.settings.find_one({"_id": "global"}) or {}
    unset = {k: "" for k in ("company_name", "default_language", "elevenlabs_model") if k in doc}
    fix = {}
    if doc.get("voice_profiles") and "female_voice_id" not in doc["voice_profiles"][0]:
        fix["voice_profiles"] = [v.model_dump() for v in Settings().voice_profiles]
    if doc.get("default_region") == "US":
        fix["default_region"] = "IN"
    if doc.get("calling_timezone") == "America/Toronto":
        fix["calling_timezone"] = "Asia/Kolkata"
    if fix or unset:
        await db.settings.update_one({"_id": "global"}, {"$set": fix, **({"$unset": unset} if unset else {})}, upsert=True)
    for old, new in LEGACY_DISPOSITION_MAP.items():
        await db.contacts.update_many({"disposition": old}, {"$set": {"disposition": new}})
        await db.call_attempts.update_many({"disposition": old}, {"$set": {"disposition": new}})


@app.on_event("startup")
async def startup():
    await db.contacts.create_index([("campaign_id", 1), ("status", 1)])
    await db.contacts.create_index([("campaign_id", 1), ("phone", 1)])
    await db.call_attempts.create_index("provider_call_id")
    await db.call_attempts.create_index("contact_id")
    await db.audit_logs.create_index([("created_at", -1)])
    await migrate_legacy()
    # recover calls orphaned by a restart (simulation tasks are in-memory)
    async for a in db.call_attempts.find({"finalized": False, "mode": "simulation"}):
        await db.call_attempts.update_one({"_id": a["_id"]}, {"$set": {
            "finalized": True, "provider_status": "interrupted", "error": "Server restarted; contact re-queued"}})
        await db.contacts.update_one({"_id": oid(a["contact_id"]), "status": "calling"},
                                     {"$set": {"status": "queued"}, "$inc": {"attempts": -1}})
    app.state.worker = asyncio.create_task(cs.worker_loop(db))


@app.on_event("shutdown")
async def shutdown():
    app.state.worker.cancel()
    client.close()
