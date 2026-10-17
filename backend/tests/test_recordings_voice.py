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
