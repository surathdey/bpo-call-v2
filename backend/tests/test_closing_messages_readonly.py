# READ-ONLY regression for deterministic closing lines (Vapi tool messages) + prompt rule 6 + webhook tool-calls result.
# No real calls, no Vapi assistant creation, no settings saves.
import asyncio
import os
import sys
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import call_service as cs  # noqa: E402
from models import CallAttempt, Campaign, Contact  # noqa: E402
from rpi_engine import resolve_language, script_lines  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
CAMPAIGN_ID = "6ad2faad17b693b316bc636b"
CALLBACK_EN = "Of course, no problem at all. We will call you back at a better time. Thank you!"


@pytest.fixture(scope="module")
def settings():
    async def _get():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            return await cs.get_settings(client[os.environ["DB_NAME"]])
        finally:
            client.close()
    return asyncio.run(_get())


def _payload(settings, state, lang_expected):
    camp = Campaign(id="0" * 24, name="TEST_unit", agent_name="Priya", prompt="")
    lang = resolve_language(state, settings.state_language_rules, settings.fallback_language) if state else lang_expected
    assert lang == lang_expected, f"state {state!r} resolved to {lang}"
    contact = Contact(id="1" * 24, campaign_id=camp.id, name="Surath Dey", phone="+919000000000",
                      bank_name="Tata Capital", state=state, language=lang)
    attempt = CallAttempt(id="2" * 24, campaign_id=camp.id, contact_id=contact.id, agent_name="Priya",
                          language=lang, spoken_name="Surath Dey", opening_line="hello")
    return cs.build_vapi_payload(settings, camp, contact, attempt), lang


CASES = [("", "en-IN"), ("Delhi", "hi-IN"), ("West Bengal", "bn-IN")]


# Closing messages attached to the file_disposition tool
class TestClosingMessages:
    @pytest.mark.parametrize("state,lang", CASES)
    def test_messages_structure(self, settings, state, lang):
        payload, lang = _payload(settings, state, lang)
        tool = payload["assistant"]["model"]["tools"][0]
        assert tool["function"]["name"] == "file_disposition"
        msgs = tool["messages"]
        complete = [m for m in msgs if m["type"] == "request-complete"]
        failed = [m for m in msgs if m["type"] == "request-failed"]
        codes = [d.code for d in settings.dispositions]
        assert len(codes) == 8, codes
        assert len(complete) == 8 and len(failed) == 1, msgs
        lines = script_lines(settings, lang, cs.call_variables(
            Campaign(name="x", agent_name="Priya"),
            Contact(campaign_id="", name="Surath Dey", phone="", bank_name="Tata Capital", state=state), "Surath Dey"))
        by_code = {m["conditions"][0]["value"]: m for m in complete}
        assert set(by_code) == set(codes)
        for d in settings.dispositions:
            m = by_code[d.code]
            assert m["conditions"] == [{"param": "disposition", "operator": "eq", "value": d.code}]
            assert m["role"] == "assistant"
            assert m["content"] == lines[d.close]
        for m in msgs:
            assert m["endCallAfterSpokenEnabled"] is True
            assert "{" not in m["content"] and "}" not in m["content"], m["content"]
            assert m["content"].strip()
        assert failed[0]["content"] == lines["denial_close"]
        assert by_code["CALLBACK_REQUESTED"]["content"] == lines["callback_close"]
        assert "representative" not in by_code["RPC_CONFIRMED"]["content"].lower()
        assert by_code["RPC_CONFIRMED"]["content"] == lines["confirmed_close"]
        if lang == "en-IN":
            assert by_code["CALLBACK_REQUESTED"]["content"] == CALLBACK_EN
        print(lang, by_code["CALLBACK_REQUESTED"]["content"], "|", by_code["RPC_CONFIRMED"]["content"])

    @pytest.mark.parametrize("state,lang", [("Delhi", "hi-IN"), ("West Bengal", "bn-IN")])
    def test_system_prompt_rule6(self, settings, state, lang):
        payload, _ = _payload(settings, state, lang)
        sp = payload["assistant"]["model"]["messages"][0]["content"]
        assert "call `file_disposition` WITHOUT speaking first" in sp
        assert '"goodbye"' in sp and '"wait a minute"' in sp
        assert "end the call (do not file a disposition)" in sp
        assert "do not call endCall" in sp


def _token():
    s = requests.get(f"{BASE_URL}/api/settings", timeout=30).json()
    url = s.get("webhook_url") or ""
    tok = parse_qs(urlparse(url).query).get("token", [None])[0]
    if not tok:
        pytest.skip("No webhook token in settings")
    return tok


# Webhook tool-calls branch (non-existent attempt -> nothing modified)
class TestWebhookToolCalls:
    def test_tool_calls_unknown_attempt(self):
        tok = _token()
        body = {"message": {"type": "tool-calls",
                            "call": {"id": "TEST_nonexistent_call", "assistant": {"metadata": {"attempt_id": "0" * 24}}},
                            "toolCallList": [{"id": "tc1", "type": "function", "function": {
                                "name": "file_disposition",
                                "arguments": {"disposition": "CALLBACK_REQUESTED", "summary": "TEST"}}}]}}
        r = requests.post(f"{BASE_URL}/api/vapi/webhook", params={"token": tok}, json=body, timeout=30)
        print(r.status_code, r.text)
        assert r.status_code == 200
        data = r.json()
        assert "results" in data, f"no results returned for unknown attempt: {data}"
        assert "closing line is spoken automatically" in data["results"][0]["result"]

    def test_bad_token(self):
        r = requests.post(f"{BASE_URL}/api/vapi/webhook", params={"token": "bad"}, json={"message": {}}, timeout=30)
        assert r.status_code == 401


# Prompt preview endpoint
class TestPromptPreview:
    def test_preview_bn(self):
        r = requests.get(f"{BASE_URL}/api/campaigns/{CAMPAIGN_ID}/prompt-preview",
                         params={"name": "Surath Dey", "bank": "Tata Capital", "state": "West Bengal"}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["language"] == "bn-IN"
        sp = d["system_prompt"]
        assert "call `file_disposition` WITHOUT speaking first" in sp
        assert '"goodbye"' in sp and '"wait a minute"' in sp
        assert "Tata Capital" in sp
        assert "{{" not in sp
