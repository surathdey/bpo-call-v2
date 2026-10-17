# Read-only regression for round-2 fixes: confirmed_close text, FINAL_DENIAL_CLOSING code, name pronunciation,
# 14-column export, Vapi payload spoken name. Safe in LIVE mode (no calls, no settings saved).
import asyncio
import csv
import io
import json
import os
import sys

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGNS = ["6ad2faad17b693b316bc636b", "6ad2fa3a17b693b316bc635f"]
EXPORT_HEADER = ["phone_number", "callee_name", "bank_name", "state", "Call ID", "Start Time", "End Time", "Duration",
                 "Call Status", "Disposition", "Category", "Summary", "Transcript", "Recording"]
MARKERS = ["representative", "प्रतिनिधि", "প্রতিনিধি"]


def _backend_imports():
    sys.path.insert(0, BACKEND_DIR)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))


async def _with_db(fn):
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    try:
        return await fn(client[os.environ["DB_NAME"]])
    finally:
        client.close()


@pytest.fixture(scope="module")
def settings_json():
    r = requests.get(f"{BASE_URL}/api/settings", timeout=30)
    assert r.status_code == 200
    return r.json()


# Confirmed close templates
class TestConfirmedClose:
    def test_bn_text(self, settings_json):
        assert "আপনার নামটা কনফার্ম করার জন্যই কলটা করছিলাম" in settings_json["script_templates"]["bn-IN"]["confirmed_close"]

    def test_hi_text(self, settings_json):
        assert "आपका नाम कन्फ़र्म करने के लिए" in settings_json["script_templates"]["hi-IN"]["confirmed_close"]

    def test_no_representative(self, settings_json):
        for lang, lines in settings_json["script_templates"].items():
            cc = lines.get("confirmed_close", "")
            for m in MARKERS:
                assert m not in cc.lower(), f"{lang} confirmed_close contains {m}"

    def test_prompt_preview(self):
        r = requests.get(f"{BASE_URL}/api/campaigns/{CAMPAIGNS[0]}/prompt-preview",
                         params={"name": "Surath Dey", "bank": "Tata Capital", "state": "West Bengal"}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["language"] == "bn-IN"
        assert "Never promise that a representative" in d["system_prompt"]
        assert "আপনার নামটা কনফার্ম করার জন্যই কলটা করছিলাম" in d["system_prompt"]


# Disposition code fix
class TestDispositionCode:
    def test_codes(self, settings_json):
        codes = [d["code"] for d in settings_json["dispositions"]]
        assert "FINAL_DENIAL_CLOSING" in codes
        assert "Final Denial Closing" not in codes
        assert settings_json["unreached_disposition"] == "FINAL_DENIAL_CLOSING"
        d = next(d for d in settings_json["dispositions"] if d["code"] == "FINAL_DENIAL_CLOSING")
        assert d.get("label") == "Final Denial Closing"

    def test_mongo_migrated(self):
        _backend_imports()

        async def q(db):
            return (await db.contacts.count_documents({"disposition": "Final Denial Closing"}),
                    await db.call_attempts.count_documents({"disposition": "Final Denial Closing"}))
        assert asyncio.run(_with_db(q)) == (0, 0)


# Name pronunciation preview endpoint
class TestPreviewName:
    def _p(self, lang):
        r = requests.post(f"{BASE_URL}/api/settings/preview-name", json={"name": "Surath Dey", "language": lang}, timeout=60)
        assert r.status_code == 200, r.text
        return r.json()["spoken"]

    def test_bn(self):
        s = self._p("bn-IN")
        print("bn spoken:", s)
        assert s and all(not c.isascii() or c == " " for c in s)
        assert any("\u0980" <= c <= "\u09FF" for c in s)

    def test_hi(self):
        s = self._p("hi-IN")
        print("hi spoken:", s)
        assert any("\u0900" <= c <= "\u097F" for c in s)

    def test_en(self):
        assert self._p("en-IN") == "Surath Dey"

    def test_bad_input(self):
        r = requests.post(f"{BASE_URL}/api/settings/preview-name", json={"name": "", "language": "bn-IN"}, timeout=30)
        assert r.status_code == 400
        r = requests.post(f"{BASE_URL}/api/settings/preview-name", json={"name": "X", "language": "fr-FR"}, timeout=30)
        assert r.status_code == 400


# spoken_name override logic (in-memory settings, nothing saved)
class TestSpokenNameOverrides:
    def _run(self, overrides, auto):
        _backend_imports()
        import call_service
        from models import Contact, PronunciationOverride

        async def go(db):
            s = await call_service.get_settings(db)
            s.pronunciation_overrides = [PronunciationOverride(**o) for o in overrides]
            s.auto_transliterate_names = auto
            ct = Contact(id="1" * 24, campaign_id="x", name="Surath Dey", phone="+919000000001", language="bn-IN")
            return await call_service.spoken_name(db, s, ct)
        return asyncio.run(_with_db(go))

    def test_word_override(self):
        assert self._run([{"name": "Dey", "language": "bn-IN", "spoken": "দে"}], False) == "Surath দে"

    def test_full_override_wins(self):
        out = self._run([{"name": "Dey", "language": "bn-IN", "spoken": "দে"},
                         {"name": "Surath Dey", "language": "bn-IN", "spoken": "সুরথ দেই"}], True)
        assert out == "সুরথ দেই"

    def test_other_language_ignored(self):
        assert self._run([{"name": "Dey", "language": "hi-IN", "spoken": "डे"}], False) == "Surath Dey"


# Export CSV (14 columns)
class TestExport:
    @pytest.mark.parametrize("cid", CAMPAIGNS)
    def test_export(self, cid):
        r = requests.get(f"{BASE_URL}/api/campaigns/{cid}/export", timeout=60)
        assert r.status_code == 200
        text = r.content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(text)))
        assert rows[0] == EXPORT_HEADER
        data = rows[1:]
        assert data, "no rows"
        completed = [x for x in data if x[8] == "completed"]
        print(cid, "rows", len(data), "completed", len(completed))
        for x in data:
            assert len(x) == 14
            if x[12]:
                assert isinstance(json.loads(x[12]), list)
        for x in completed:
            assert x[10].strip(), f"Empty category {x[4]}"
            assert x[11].strip(), f"Empty summary {x[4]}"
        recs = [x[13] for x in data if x[13]]
        assert recs, "no recording links"
        for url in recs[:2]:
            assert url.startswith(f"{BASE_URL}/api/recordings/")
            rr = requests.get(url, timeout=90)
            assert rr.status_code == 200
            assert rr.headers["content-type"].startswith("audio/wav")


# Vapi payload builder (dict only, NO call)
class TestVapiPayloadSpokenName:
    def test_payload(self):
        _backend_imports()
        import call_service
        from models import CallAttempt, Campaign, Contact
        from rpi_engine import script_lines
        settings = asyncio.run(_with_db(call_service.get_settings))
        camp = Campaign(id="0" * 24, name="x", agent_name="Ria", voice_gender="female")
        ct = Contact(id="1" * 24, campaign_id="x", name="Surath Dey", phone="+919000000001",
                     bank_name="Tata Capital", state="West Bengal", language="bn-IN")
        spoken = "সুরথ দে"
        lines = script_lines(settings, "bn-IN", call_service.call_variables(camp, ct, spoken))
        att = CallAttempt(id="2" * 24, campaign_id="x", contact_id="y", spoken_name=spoken, opening_line=lines["opening"],
                          voice_id=call_service.resolve_voice(settings, camp, "bn-IN"))
        p = call_service.build_vapi_payload(settings, camp, ct, att)
        assert spoken in p["assistant"]["firstMessage"]
        assert spoken in p["assistant"]["model"]["messages"][0]["content"]
        assert p["customer"]["name"] == "Surath Dey"
