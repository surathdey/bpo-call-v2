# Read-only regression: recording proxy + Bengali voice profile (safe in LIVE mode, no campaign actions)
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


# Recording proxy endpoint
class TestRecordings:
    @pytest.mark.parametrize("att", ["6ad2fac617b693b316bc6370", "6ad2fa4e17b693b316bc6364"])
    def test_recording_ok(self, att):
        r = requests.get(f"{BASE_URL}/api/recordings/{att}", timeout=90)
        assert r.status_code == 200, r.text[:200]
        assert r.headers["content-type"].startswith("audio/wav")
        assert len(r.content) > 100_000
        assert r.content[:4] == b"RIFF"

    def test_invalid_id_404(self):
        r = requests.get(f"{BASE_URL}/api/recordings/not-an-id", timeout=30)
        assert r.status_code == 404

    def test_nonexistent_id_404(self):
        r = requests.get(f"{BASE_URL}/api/recordings/000000000000000000000000", timeout=30)
        assert r.status_code == 404

    def test_attempt_without_recording_404(self):
        # find an attempt with no recording via contact detail APIs
        camps = requests.get(f"{BASE_URL}/api/campaigns", timeout=30).json()
        camps = camps if isinstance(camps, list) else camps.get("campaigns", camps.get("items", []))
        for c in camps:
            cid = c.get("id")
            cr = requests.get(f"{BASE_URL}/api/campaigns/{cid}/contacts", timeout=30)
            if cr.status_code != 200:
                continue
            data = cr.json()
            contacts = data if isinstance(data, list) else data.get("contacts", data.get("items", []))
            for ct in contacts[:20]:
                d = requests.get(f"{BASE_URL}/api/contacts/{ct['id']}", timeout=30).json()
                for a in d.get("attempts", []):
                    if not a.get("recording_url"):
                        r = requests.get(f"{BASE_URL}/api/recordings/{a['id']}", timeout=30)
                        assert r.status_code == 404
                        return
        pytest.skip("No attempt without recording found")


# Bengali voice profile in settings
class TestSettingsVoices:
    def test_bengali_profile(self):
        r = requests.get(f"{BASE_URL}/api/settings", timeout=30)
        assert r.status_code == 200
        s = r.json()
        profiles = s.get("voice_profiles") or s.get("settings", {}).get("voice_profiles")
        bn = next(p for p in profiles if p["language"] == "bn-IN")
        assert bn["tts_provider"] == "11labs"
        assert bn["female_voice_id"] == "611e0Wo6wEi3GcpkO5it"
        assert bn["male_voice_id"] == "GuSivqtqi1qfWxEuGhqa"
        assert bn["tts_model"] == "eleven_v3"
        assert "Ananya" in bn["female_voice_name"]
        assert "Dipankar" in bn["male_voice_name"]
        assert "_id" not in s


# Hindi / English voice profiles in settings (eleven_v3 for hi-IN)
class TestSettingsVoicesHiEn:
    def _profiles(self):
        s = requests.get(f"{BASE_URL}/api/settings", timeout=30).json()
        return s.get("voice_profiles") or s.get("settings", {}).get("voice_profiles")

    def test_hindi_profile(self):
        hi = next(p for p in self._profiles() if p["language"] == "hi-IN")
        assert hi["tts_provider"] == "11labs"
        assert hi["tts_model"] == "eleven_v3"
        assert hi["female_voice_id"] == "1qEiC6qsybMkmnNdVMbK"
        assert hi["male_voice_id"] == "zT03pEAEi0VHKciJODfn"

    def test_english_profile_unchanged(self):
        en = next(p for p in self._profiles() if p["language"] == "en-IN")
        assert en["tts_model"] == "eleven_turbo_v2_5"


# Vapi payload builder (dict only, places NO call)
class TestVapiPayloadModel:
    @pytest.mark.parametrize("lang,state,gender,vid", [
        ("hi-IN", "Delhi", "female", "1qEiC6qsybMkmnNdVMbK"),
        ("hi-IN", "Delhi", "male", "zT03pEAEi0VHKciJODfn"),
        ("bn-IN", "West Bengal", "female", "611e0Wo6wEi3GcpkO5it"),
        ("bn-IN", "West Bengal", "male", "GuSivqtqi1qfWxEuGhqa"),
    ])
    def test_payload_voice_model(self, lang, state, gender, vid):
        import asyncio, sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        from motor.motor_asyncio import AsyncIOMotorClient
        import call_service
        from models import Campaign, Contact, CallAttempt

        async def run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            try:
                return await call_service.get_settings(client[os.environ["DB_NAME"]])
            finally:
                client.close()
        settings = asyncio.run(run())
        camp = Campaign(id="0" * 24, name="x", agent_name="Ria", voice_gender=gender)
        ct = Contact(id="1" * 24, campaign_id="x", name="Amit", phone="+919000000001",
                     bank_name="SBI", state=state, language=lang)
        att = CallAttempt(id="2" * 24, campaign_id="x", contact_id="y",
                          voice_id=call_service.resolve_voice(settings, camp, lang))
        voice = call_service.build_vapi_payload(settings, camp, ct, att)["assistant"]["voice"]
        assert voice["provider"] == "11labs"
        assert voice["model"] == "eleven_v3"
        assert voice["voiceId"] == vid
