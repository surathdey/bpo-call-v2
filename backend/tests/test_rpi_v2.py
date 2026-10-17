# RPI v2 regression tests: settings, campaigns(agent_name), CSV 4-col, state->language, simulation, export, webhook tool-calls
# NOTE: call_mode must stay 'simulation'. Never toggle live mode in these tests.
import csv
import io
import json
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
DISPS = ["RPC_CONFIRMED", "CPC_CONFIRMED", "CALLBACK_REQUESTED", "FINAL_DENIAL",
         "Final Denial Closing", "HOSTILE", "DECEASED_CASE", "DNC_ESCALATION"]
EXPORT_COLS = ["phone_number", "callee_name", "bank_name", "state", "Call ID", "Start Time", "End Time", "Duration",
               "Call Status", "Disposition", "Category", "Summary", "Transcript", "Recording"]
SAMPLE = open(os.path.join(os.path.dirname(__file__), "sample_v2.csv"), "rb").read()


def _mongo():
    env = {}
    for line in open("/app/backend/.env"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            env[k] = v.strip('"')
    return MongoClient(env["MONGO_URL"])[env["DB_NAME"]]


@pytest.fixture(scope="session")
def s():
    return requests.Session()


@pytest.fixture(scope="session", autouse=True)
def original_settings(s):
    orig = s.get(f"{API}/settings").json()
    assert orig["call_mode"] == "simulation", "ABORT: settings must be in simulation mode"
    yield orig
    # restore editable fields
    restore = {k: orig[k] for k in ("state_language_rules", "fallback_language", "voice_profiles", "dispositions",
                                     "unreached_disposition", "emotion_guidelines", "script_templates") if k in orig}
    r = s.put(f"{API}/settings", json=restore)
    assert r.status_code == 200, r.text
    assert s.get(f"{API}/settings").json()["call_mode"] == "simulation"


def new_campaign(s, agent="TEST_Priya"):
    r = s.post(f"{API}/campaigns", json={"name": f"TEST_{uuid.uuid4().hex[:6]}", "agent_name": agent})
    assert r.status_code == 200, r.text
    return r.json()


def upload(s, cid, content, path="import"):
    return s.post(f"{API}/campaigns/{cid}/contacts/{path}", files={"file": ("t.csv", content, "text/csv")})


# ---- Settings ----
class TestSettings:
    def test_meta_and_defaults(self, s, original_settings):
        st = original_settings
        assert sorted(v["language"] for v in st["voice_profiles"]) == ["bn-IN", "en-IN", "hi-IN"]
        for v in st["voice_profiles"]:
            for k in ("female_voice_id", "male_voice_id", "tts_model", "stt_provider", "stt_model", "stt_language"):
                assert k in v
        assert {"state": "West Bengal", "language": "bn-IN"} in st["state_language_rules"]
        assert st["fallback_language"] == "hi-IN"
        assert sorted(d["code"] for d in st["dispositions"]) == sorted(DISPS)
        assert "company_name" not in st
        m = s.get(f"{API}/meta").json()
        assert m["dispositions"] == DISPS or sorted(m["dispositions"]) == sorted(DISPS)
        assert [l["code"] for l in m["languages"]] == ["en-IN", "bn-IN", "hi-IN"]

    def test_duplicate_state_rule_rejected(self, s):
        r = s.put(f"{API}/settings", json={"state_language_rules": [{"state": "West Bengal", "language": "bn-IN"},
                                                                    {"state": "west bengal ", "language": "hi-IN"}]})
        assert r.status_code == 400

    def test_invalid_language_rejected(self, s):
        r = s.put(f"{API}/settings", json={"state_language_rules": [{"state": "Goa", "language": "fr-FR"}]})
        assert r.status_code == 400
        r = s.put(f"{API}/settings", json={"fallback_language": "en-US"})
        assert r.status_code == 400

    def test_opening_without_agent_name_rejected(self, s):
        r = s.put(f"{API}/settings", json={"script_templates": {"hi-IN": {"opening": "Namaste from {{bank_name}}"}}})
        assert r.status_code == 400

    def test_voice_profiles_count_enforced(self, s, original_settings):
        r = s.put(f"{API}/settings", json={"voice_profiles": original_settings["voice_profiles"][:2]})
        assert r.status_code == 400

    def test_script_and_emotion_persist(self, s, original_settings):
        r = s.put(f"{API}/settings", json={"emotion_guidelines": "TEST_EMO be kind",
                                          "script_templates": {"bn-IN": {"opening": "TEST {{agent_name}} {{bank_name}} {{customer_name}}"}}})
        assert r.status_code == 200, r.text
        g = s.get(f"{API}/settings").json()
        assert g["emotion_guidelines"] == "TEST_EMO be kind"
        assert g["script_templates"]["bn-IN"]["opening"].startswith("TEST {{agent_name}}")
        s.put(f"{API}/settings", json={"emotion_guidelines": original_settings["emotion_guidelines"],
                                       "script_templates": original_settings.get("script_templates") or {}})


# ---- Campaign ----
class TestCampaign:
    def test_agent_name_required(self, s):
        r = s.post(f"{API}/campaigns", json={"name": "TEST_noagent"})
        assert r.status_code == 422

    def test_scripts_contain_agent_name(self, s):
        c = new_campaign(s, "TEST_Anjali")
        d = s.get(f"{API}/campaigns/{c['id']}").json()
        assert set(d["scripts"]) == {"en-IN", "bn-IN", "hi-IN"}
        for lang, sc in d["scripts"].items():
            assert "TEST_Anjali" in sc["opening"], (lang, sc["opening"])
        assert "RevLoop" not in json.dumps(d["scripts"])


# ---- CSV ----
class TestCsv:
    def test_validate_rejects_missing_phone_and_bank(self, s):
        c = new_campaign(s)
        content = b"phone_number,name,bank_name,state/province\n,No Phone,HDFC,Delhi\n9000000011,No Bank,,Delhi\n9000000012,Good Row,SBI,west bengal\n"
        r = upload(s, c["id"], content, "validate")
        assert r.status_code == 200
        rep = r.json()
        assert rep["valid_count"] == 1 and rep["invalid_count"] == 2
        reasons = {i["name"]: i["reasons"] for i in rep["invalid"]}
        assert "Missing phone_number" in reasons["No Phone"]
        assert "Missing bank_name" in reasons["No Bank"]
        assert rep["valid"][0]["language"] == "bn-IN"

    def test_header_errors(self, s):
        c = new_campaign(s)
        r = upload(s, c["id"], b"phone_number,name,state/province\n9000000013,X,Delhi\n", "validate")
        assert r.status_code == 200
        assert any("bank_name" in e for e in r.json()["header_errors"])
        r = upload(s, c["id"], b"phone_number,name,state/province\n9000000013,X,Delhi\n", "import")
        assert r.status_code == 400

    def test_import_sample_languages(self, s):
        c = new_campaign(s)
        r = upload(s, c["id"], SAMPLE)
        assert r.status_code == 200 and r.json()["imported"] == 6
        rows = s.get(f"{API}/campaigns/{c['id']}/contacts").json()
        lang = {x["state"]: x["language"] for x in rows}
        assert lang["West Bengal"] == "bn-IN" and lang["west bengal"] == "bn-IN"
        assert lang["Maharashtra"] == "hi-IN" and lang["Delhi"] == "hi-IN"


# ---- Simulation end-to-end + export + retry ----
@pytest.fixture(scope="module")
def sim_campaign(s, original_settings):
    c = new_campaign(s, "TEST_Kavya")
    assert upload(s, c["id"], SAMPLE).json()["imported"] == 6
    # state rule change before dialing: Maharashtra -> en-IN
    rules = original_settings["state_language_rules"] + [{"state": "Maharashtra", "language": "en-IN"}]
    assert s.put(f"{API}/settings", json={"state_language_rules": rules}).status_code == 200
    r = s.post(f"{API}/campaigns/{c['id']}/launch")
    assert r.status_code == 200, r.text
    for _ in range(60):
        d = s.get(f"{API}/campaigns/{c['id']}").json()
        if d["stats"]["completed"] == 6:
            break
        time.sleep(3)
    s.put(f"{API}/settings", json={"state_language_rules": original_settings["state_language_rules"]})
    return d


class TestSimulation:
    def test_all_completed_with_canonical_dispositions(self, s, sim_campaign):
        assert sim_campaign["stats"]["completed"] == 6
        rows = s.get(f"{API}/campaigns/{sim_campaign['id']}/contacts").json()
        for r in rows:
            assert r["disposition"] in DISPS
        assert sum(sim_campaign["stats"][d] for d in DISPS) == 6

    def test_state_rule_applied_at_dial_time(self, s, sim_campaign):
        rows = s.get(f"{API}/campaigns/{sim_campaign['id']}/contacts").json()
        m = next(r for r in rows if r["state"] == "Maharashtra")
        assert m["language"] == "en-IN"

    def test_campaign_list_bucket_counts(self, s, sim_campaign):
        lst = s.get(f"{API}/campaigns").json()
        c = next(x for x in lst if x["id"] == sim_campaign["id"])
        for d in DISPS:
            assert d in c["stats"]

    def test_export_columns_and_transcript(self, s, sim_campaign):
        r = s.get(f"{API}/campaigns/{sim_campaign['id']}/export")
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        assert rows[0] == EXPORT_COLS
        assert len(rows) == 7
        for row in rows[1:]:
            assert len(row) == 14
            assert isinstance(json.loads(row[12]), list)
            assert row[9] in DISPS
            assert row[13] == ""  # simulation has no recording

    def test_export_filter_final_denial_closing(self, s, sim_campaign):
        r = s.get(f"{API}/campaigns/{sim_campaign['id']}/export", params={"disposition": "Final Denial Closing"})
        assert r.status_code == 200
        rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        assert rows[0] == EXPORT_COLS
        assert all(row[9] == "Final Denial Closing" for row in rows[1:])
        assert len(rows) - 1 == sim_campaign["stats"]["Final Denial Closing"]

    def test_recording_404(self, s, sim_campaign):
        calls = s.get(f"{API}/campaigns/{sim_campaign['id']}/calls").json()
        assert s.get(f"{API}/recordings/{calls[0]['id']}").status_code == 404

    def test_retry_selected_excludes_rpc(self, s, sim_campaign):
        rows = s.get(f"{API}/campaigns/{sim_campaign['id']}/contacts").json()
        rpc = [r["id"] for r in rows if r["disposition"] == "RPC_CONFIRMED"]
        if not rpc:
            pytest.skip("no RPC contact in random simulation")
        r = s.post(f"{API}/campaigns/{sim_campaign['id']}/retry", json={"contact_ids": rpc})
        assert r.json()["requeued"] == 0

    def test_retry_unreached(self, s, sim_campaign):
        rows = s.get(f"{API}/campaigns/{sim_campaign['id']}/contacts").json()
        unreached = [r for r in rows if r.get("last_call_status") in ("no-answer", "voicemail", "busy", "failed")]
        r = s.post(f"{API}/campaigns/{sim_campaign['id']}/retry", json={})
        assert r.status_code == 200
        assert r.json()["requeued"] + r.json()["skipped_retry_limit"] == len(unreached)


# ---- Webhook ----
class TestWebhook:
    def test_tool_call_then_end_of_call(self, s):
        db = _mongo()
        token = db.settings.find_one({"_id": "global"})["webhook_token"]
        c = new_campaign(s, "TEST_Hook")
        upload(s, c["id"], b"phone_number,name,bank_name,state/province\n9000000077,Hook User,SBI,Delhi\n")
        ct = s.get(f"{API}/campaigns/{c['id']}/contacts").json()[0]
        pcid = f"test-xyz-{uuid.uuid4().hex[:6]}"
        att = {"campaign_id": c["id"], "contact_id": ct["id"], "attempt_number": 1, "mode": "live",
               "customer_name": "Hook User", "phone": ct["phone"], "bank_name": "SBI", "state": "Delhi",
               "agent_name": "TEST_Hook", "language": "hi-IN", "voice_id": "x", "opening_line": "x",
               "provider_status": "in-progress", "provider_call_id": pcid, "finalized": False, "transcript": [],
               "created_at": "2026-01-01T00:00:00+00:00", "webhook_events": 0}
        aid = str(db.call_attempts.insert_one(att).inserted_id)
        db.contacts.update_one({"_id": ObjectId(ct["id"])}, {"$set": {"status": "calling", "last_attempt_id": aid, "attempts": 1}})
        url = f"{API}/vapi/webhook?token={token}"
        assert s.post(f"{API}/vapi/webhook?token=bad", json={}).status_code == 401
        r = s.post(url, json={"message": {"type": "tool-calls", "call": {"id": pcid}, "toolCallList": [
            {"id": "tc1", "function": {"name": "file_disposition", "arguments": {"disposition": "HOSTILE", "summary": "x"}}}]}})
        assert r.status_code == 200, r.text
        assert r.json()["results"][0]["toolCallId"] == "tc1"
        assert db.call_attempts.find_one({"_id": ObjectId(aid)})["agent_disposition"] == "HOSTILE"
        r = s.post(url, json={"message": {"type": "end-of-call-report", "call": {"id": pcid}, "endedReason": "customer-ended-call",
                                          "artifact": {"recordingUrl": "https://example.com/rec.wav", "messages": [
                                              {"role": "bot", "message": "Namaste"}, {"role": "user", "message": "बकवास बंद करो पागल"}]}}})
        assert r.status_code == 200
        a = db.call_attempts.find_one({"_id": ObjectId(aid)})
        assert a["disposition"] == "HOSTILE" and a["classification"]["source"] == "agent"
        ex = s.get(f"{API}/campaigns/{c['id']}/export").content.decode("utf-8-sig")
        row = list(csv.reader(io.StringIO(ex)))[1]
        assert row[13].endswith(f"/api/recordings/{aid}") and row[13].startswith("https://"), row[13]
        assert row[4] == pcid
