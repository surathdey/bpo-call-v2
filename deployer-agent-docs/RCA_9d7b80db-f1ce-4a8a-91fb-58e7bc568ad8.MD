# RCA — "Production serving stale code" (identity-check-ops)

## Verdict
**Production is NOT stale. The latest code is live. No redeploy is needed.**
The symptom is almost certainly a **stale frontend bundle cached in the browser/edge**, not a stale deploy.

## Live URL
https://identity-check-ops.emergent.host  (reachable, GET /api/settings → 200)

## Latest deployment status
- Latest run: `9d7b80db-f1ce-4a8a-91fb-58e7bc568ad8` — type **redeploy**, status **SUCCEEDED**, completed **2026-10-17T05:59:29Z**.
- Image live: `...customers-app@sha256:54b74cc768bc78e71bc28f98e4fce7807f210dedf060d67314a2ec6836772dea` (this run's image == the deployment's active image).
- Build state: **SUCCEEDED** (CodeBuild `d35eb6c4...`). Frontend compiled ("Compiled successfully") and copied into the image; backend image pushed.
- Run history shows exactly **two** runs: initial `349eb507` (succeeded 05:29:58Z) + redeploy `9d7b80db` (succeeded 05:59:29Z). **There is no failed or in-progress third run.** The "published twice" = initial + this one redeploy; both are green.

## Commit that was built
The pipeline snapshots the **preview pod's working tree** at pull time and strips `.git`, so the deployed artifact carries **no git SHA** — I cannot read back the literal commit hash. However, the exact source that was built (verified in a sandbox restored from this run's pulled source) contains **every** Round-3 change you listed. Since 93ec829 is "Auto-generated changes" on top of de06871 (Round 3 fixes) and all Round-3 features are present and live, production functionally reflects the latest code. (Caveat: if any change was committed to the preview pod *after* ~05:55Z when pull_source ran, it would not be included — but all listed features are present, so nothing is missing.)

## Evidence the NEW backend is running (not stale)
1. **New endpoints exist in prod:**
   - `GET /api/settings/reset-scripts` → **405 Method Not Allowed** (path exists, POST-only).
   - `GET /api/settings/preview-name` → **405 Method Not Allowed** (path exists, POST-only).
   - Source confirms `@api.post("/settings/reset-scripts")` (server.py L174) and `@api.post("/settings/preview-name")` (L182).
2. **Startup migration ran against the PROD DB:** `migrate_legacy()` (server.py L561) is invoked in the `@app.on_event("startup")` handler (L600). The prod `settings` doc `_id:"global"` has `updated_at = 2026-10-17T06:01:38Z` — **after** promote (05:59:29Z) — i.e. a new pod booted with new code and rewrote the templates.
3. **Template content is migrated/clean (requirement 1):** en-IN, hi-IN, bn-IN each now contain a `reverify` key; none of the `script_templates` contain `representative` / `प्रतिनिधि` / `প্রতিনিধি`. (The only remaining "representative" strings are in `default_prompt`/`rpi_engine.py`/`defaults.py` guard markers and test files — not in `script_templates`, which is what the requirement targets.)

## Evidence the NEW frontend was built (requirement 4)
- Build log: `[frontend-build] Compiled successfully`, `build/` copied to `/frontend-output` and into the image.
- Built frontend source contains: `Reset scripts to defaults` button (SettingsPage.jsx L179), `FINAL_DENIAL_CLOSING` (Badges.jsx, CampaignsPage.jsx, lib/api.js), and `reverify` script fields (rendered dynamically from the script keys).
- Note: this is a **Cloudflare frontend** served from R2 with content-hashed assets. The index.html currently served references `/static/js/main.3fbdeac5.js`. A browser or edge holding the previous `index.html`/bundle will keep showing the OLD Settings UI even though the backend and R2 are current — this is the most likely explanation for the "stale" report.

## openapi.json note (requirement 2)
`/api/settings/reset-scripts` definitely exists (405 above). You could not see it in `/api/openapi.json` because that returns **404** and `/openapi.json` returns the **frontend SPA HTML**: the Cloudflare worker routes all non-`/api` paths to the R2 frontend, and FastAPI serves its schema at the root `/openapi.json` (which never reaches the backend through the worker). This is a routing artifact of the Cloudflare frontend, **not** a missing endpoint — verify endpoints via a 405-on-GET probe instead.

## Minor observation (not the reported issue)
`settings.global.webhook_base_url` still points at the preview URL (`https://identity-check-ops.preview.emergentagent.com`). This is stored DB data, not code; if prod webhooks must hit the prod host, update that value. Not related to the stale-code report.

## Action
- **No redeploy required** — prod already runs the latest code.
- Have the user do a **hard refresh / open in incognito** (or clear cache) to drop the stale frontend bundle, then re-check the Settings page.
