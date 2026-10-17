# Iteration 10: Vapi webhook tool-calls handling for unknown/known attempts. No real calls, no settings saves.
import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from bson import ObjectId
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
URL = f"{BASE_URL}/api/vapi/webhook"
UNKNOWN_CALL = "TEST_unknown_call_iter10"


def _db_run(fn):
    async def _w():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            return await fn(c[os.environ["DB_NAME"]])
        finally:
            c.close()
    return asyncio.run(_w())


@pytest.fixture(scope="module")
def token():
    r = requests.get(f"{BASE_URL}/api/settings", timeout=20)
    assert r.status_code == 200
    wh = r.json().get("webhook_url")
    assert wh, "webhook_url missing"
    return parse_qs(urlparse(wh).query)["token"][0]


def _tc(call_id, name="file_disposition", args=None, tcid="tc_1", meta=None):
    call = {"id": call_id}
    if meta:
        call["assistant"] = {"metadata": {"attempt_id": meta}}
    return {"message": {"type": "tool-calls", "call": call, "toolCallList": [
        {"id": tcid, "type": "function", "function": {"name": name, "arguments": args or {}}}]}}


def _counts():
    async def f(db):
        return (await db.call_attempts.count_documents({}),
                await db.audit_logs.count_documents({"event": "agent_disposition_filed"}))
    return _db_run(f)


# --- unknown call tool-calls ---
def test_unknown_call_valid_disposition_returns_result_no_db_change(token):
    before = _counts()
    r = requests.post(URL, params={"token": token}, json=_tc(UNKNOWN_CALL, args={
        "disposition": "CALLBACK_REQUESTED", "summary": "TEST"}, tcid="tc_unknown"), timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["results"][0]["toolCallId"] == "tc_unknown"
    assert "closing line is spoken automatically" in d["results"][0]["result"]
    assert _counts() == before


def test_unknown_call_string_arguments(token):
    r = requests.post(URL, params={"token": token}, json=_tc(
        UNKNOWN_CALL, args='{"disposition":"RPC_CONFIRMED"}'), timeout=20)
    assert r.status_code == 200
    assert "closing line is spoken automatically" in r.json()["results"][0]["result"]


def test_invalid_disposition(token):
    r = requests.post(URL, params={"token": token}, json=_tc(UNKNOWN_CALL, args={"disposition": "BOGUS"}), timeout=20)
    assert r.status_code == 200
    assert "Invalid disposition" in r.json()["results"][0]["result"]


def test_unknown_tool(token):
    r = requests.post(URL, params={"token": token}, json=_tc(UNKNOWN_CALL, name="foo"), timeout=20)
    assert r.status_code == 200
    assert "Unknown tool" in r.json()["results"][0]["result"]


def test_bad_token_401():
    r = requests.post(URL, params={"token": "bad"}, json=_tc(UNKNOWN_CALL), timeout=20)
    assert r.status_code == 401


def test_status_update_unknown_call_ignored(token):
    r = requests.post(URL, params={"token": token}, json={"message": {
        "type": "status-update", "status": "in-progress", "call": {"id": UNKNOWN_CALL}}}, timeout=20)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "ignored": "unknown call"}


def test_multiple_tool_calls_one_result_each(token):
    body = _tc(UNKNOWN_CALL, args={"disposition": "RPC_CONFIRMED"}, tcid="a")
    body["message"]["toolCallList"].append({"id": "b", "function": {"name": "x", "arguments": {}}})
    r = requests.post(URL, params={"token": token}, json=body, timeout=20)
    res = r.json()["results"]
    assert [x["toolCallId"] for x in res] == ["a", "b"]


# --- known attempt regression: isolated TEST_ attempt inserted directly (not live data), then removed ---
@pytest.fixture
def test_attempt():
    oid = ObjectId()
    pcid = f"TEST_pcid_{oid}"

    async def ins(db):
        await db.call_attempts.insert_one({"_id": oid, "campaign_id": "TEST_campaign_iter10", "contact_id": "TEST_c",
                                           "provider_call_id": pcid, "finalized": False, "mode": "simulated",
                                           "created_at": datetime.now(timezone.utc).isoformat()})
    _db_run(ins)
    yield oid, pcid

    async def rm(db):
        await db.call_attempts.delete_one({"_id": oid})
        await db.audit_logs.delete_many({"campaign_id": "TEST_campaign_iter10"})
    _db_run(rm)


def test_known_attempt_sets_agent_disposition(token, test_attempt):
    oid, pcid = test_attempt
    r = requests.post(URL, params={"token": token}, json=_tc(pcid, args={
        "disposition": "CALLBACK_REQUESTED", "summary": "TEST summary"}), timeout=20)
    assert r.status_code == 200
    assert "closing line is spoken automatically" in r.json()["results"][0]["result"]

    async def get(db):
        return (await db.call_attempts.find_one({"_id": oid}),
                await db.audit_logs.count_documents({"campaign_id": "TEST_campaign_iter10",
                                                     "event": "agent_disposition_filed"}))
    doc, audits = _db_run(get)
    assert doc["agent_disposition"] == "CALLBACK_REQUESTED"
    assert doc["agent_summary"] == "TEST summary"
    assert audits == 1


def test_known_attempt_via_metadata(token, test_attempt):
    oid, _ = test_attempt
    r = requests.post(URL, params={"token": token}, json=_tc("TEST_nomatch", args={
        "disposition": "RPC_CONFIRMED"}, meta=str(oid)), timeout=20)
    assert r.status_code == 200

    async def get(db):
        return await db.call_attempts.find_one({"_id": oid})
    assert _db_run(get)["agent_disposition"] == "RPC_CONFIRMED"
