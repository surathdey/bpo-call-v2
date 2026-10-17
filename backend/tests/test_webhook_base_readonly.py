# READ-ONLY regression for iteration 8: webhook base / export Recording host (LIVE Vapi - no writes)
import csv, io, os
import pytest, requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
CAMPAIGN = "6ad2faad17b693b316bc636b"


@pytest.fixture(scope="module")
def export_rows():
    r = requests.get(f"{BASE_URL}/api/campaigns/{CAMPAIGN}/export", timeout=60)
    assert r.status_code == 200, r.text[:300]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert rows
    return rows


# Settings: webhook base equals preview origin
def test_settings_webhook_base_matches_preview():
    r = requests.get(f"{BASE_URL}/api/settings", timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["webhook_base_url"].rstrip("/") == BASE_URL
    assert d.get("webhook_url", "").startswith(BASE_URL + "/api/")
    assert "vapi_api_key" not in d


# Export: Recording links use the browsing host
def test_export_recording_links_use_preview_host(export_rows):
    recs = [r["Recording"] for r in export_rows if r.get("Recording")]
    assert recs, "no recording links in export"
    for link in recs:
        assert link.startswith(f"{BASE_URL}/api/recordings/"), link


def test_export_recording_link_serves_wav(export_rows):
    recs = [r["Recording"] for r in export_rows if r.get("Recording")]
    ok = False
    for link in recs[:5]:
        r = requests.get(link, timeout=60, stream=True)
        if r.status_code == 200 and "audio/wav" in r.headers.get("content-type", ""):
            ok = True
            r.close()
            break
        r.close()
    assert ok, "no recording link returned 200 audio/wav"
