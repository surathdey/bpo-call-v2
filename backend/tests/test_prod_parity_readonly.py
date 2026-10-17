# STRICTLY READ-ONLY prod vs preview parity checks for Round 3 fixes (LIVE mode - no writes besides preview-name/export audit)
import csv
import io
import os
import re
import pytest
import requests

PROD = "https://identity-check-ops.emergent.host"
PREVIEW = os.environ.get("REACT_APP_BACKEND_URL", "https://identity-check-ops.preview.emergentagent.com").rstrip("/")
ENVS = {"prod": PROD, "preview": PREVIEW}
EXPORT_HEADER = ["phone_number", "callee_name", "bank_name", "state", "Call ID", "Start Time", "End Time", "Duration",
                 "Call Status", "Disposition", "Category", "Summary", "Transcript", "Recording"]


@pytest.fixture(params=list(ENVS), scope="module")
def base(request):
    return ENVS[request.param]


def _settings(base):
    r = requests.get(f"{base}/api/settings", timeout=30)
    assert r.status_code == 200, r.text[:300]
    return r.json()


# Settings: script templates / dispositions / voice profiles
def test_script_templates_reverify_and_no_representative(base):
    st = _settings(base)["script_templates"]
    for lang in ("en-IN", "hi-IN", "bn-IN"):
        assert lang in st, f"{lang} missing"
        assert "reverify" in st[lang] and st[lang]["reverify"].strip(), f"{lang} reverify missing"
        blob = " ".join(str(v) for v in st[lang].values())
        for bad in ("representative", "प्रतिनिधि", "প্রতিনিধি"):
            assert bad not in blob, f"{lang} contains {bad}"


def test_dispositions_final_denial(base):
    s = _settings(base)
    codes = [d.get("code") if isinstance(d, dict) else d for d in s["dispositions"]]
    assert "FINAL_DENIAL_CLOSING" in codes
    assert s["unreached_disposition"] == "FINAL_DENIAL_CLOSING"


def test_voice_profiles_v3(base):
    vp = _settings(base)["voice_profiles"]
    vp = {p["language"]: p for p in vp} if isinstance(vp, list) else vp
    for lang in ("hi-IN", "bn-IN"):
        assert vp[lang]["tts_model"] == "eleven_v3", f"{lang}: {vp[lang].get('tts_model')}"
    ids = {vp["bn-IN"].get("male_voice_id"), vp["bn-IN"].get("female_voice_id")}
    assert ids == {"611e0Wo6wEi3GcpkO5it", "GuSivqtqi1qfWxEuGhqa"}, ids


# Name preview + reset-scripts route existence
def test_preview_name_bengali(base):
    r = requests.post(f"{base}/api/settings/preview-name", json={"name": "Surath Dey", "language": "bn-IN"}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    spoken = r.json()["spoken"]
    print(base, "spoken:", spoken)
    assert re.search(r"[\u0980-\u09FF]", spoken), spoken


def test_reset_scripts_route_exists(base):
    r = requests.get(f"{base}/api/settings/reset-scripts", timeout=30)
    assert r.status_code == 405, r.status_code


# Campaign prompt preview + export header
def _campaigns(base):
    r = requests.get(f"{base}/api/campaigns", timeout=30)
    assert r.status_code == 200
    cs = r.json()
    assert cs, "no campaigns"
    return cs


def test_prompt_preview(base):
    c = _campaigns(base)[0]
    r = requests.get(f"{base}/api/campaigns/{c['id']}/prompt-preview",
                     params={"name": "Surath Dey", "bank": "Tata Capital", "state": "West Bengal"}, timeout=60)
    assert r.status_code == 200
    sp = r.json()["system_prompt"]
    assert "RPI CONVERSATION FLOW" in sp
    assert "REVERIFY" in sp
    assert "OPERATOR INSTRUCTIONS (high priority" in sp
    assert "((" not in sp
    assert r.json()["language"] == "bn-IN"


def test_export_header(base):
    cs = _campaigns(base)
    c = next((x for x in cs if (x.get("stats") or {}).get("total", 0) or (x.get("stats") or {}).get("contacts", 0)), cs[0])
    r = requests.get(f"{base}/api/campaigns/{c['id']}/export", timeout=60)
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    print(base, c["name"], "rows:", len(rows) - 1)
    assert rows[0] == EXPORT_HEADER, rows[0]
