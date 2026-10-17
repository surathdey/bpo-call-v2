import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Copy, KeyRound, PlugZap, RefreshCw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, errMsg, DISPOSITIONS } from "@/lib/api";
import { DispositionsEditor, FallbackLanguage, ScriptsEditor, StateRulesEditor, VoiceProfilesTable } from "@/components/rpi/SettingsSections";

const Section = ({ title, desc, children, testId }) => (
  <section className="rise grid gap-6 border-b border-slate-800 py-8 lg:grid-cols-[280px_1fr]" data-testid={testId}>
    <div>
      <h2 className="font-display text-base font-semibold text-slate-100">{title}</h2>
      <p className="mt-1 text-sm text-slate-500">{desc}</p>
    </div>
    <div className="min-w-0 space-y-4">{children}</div>
  </section>
);

const Field = ({ label, hint, children }) => (
  <div className="space-y-1.5">
    <Label className="text-slate-300">{label}</Label>
    {children}
    {hint && <p className="text-xs text-slate-500">{hint}</p>}
  </div>
);

export default function SettingsPage() {
  const [s, setS] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [dnc, setDnc] = useState("");
  const [saving, setSaving] = useState(false);

  const load = (data) => { setS(data); setDnc((data.dnc_numbers || []).join("\n")); };
  useEffect(() => { api.get("/settings").then((r) => load(r.data)); }, []);
  if (!s) return <div className="text-sm text-slate-500">Loading settings…</div>;

  const set = (k) => (v) => setS((p) => ({ ...p, [k]: v?.target ? v.target.value : v }));
  const num = (k) => (e) => setS((p) => ({ ...p, [k]: e.target.value === "" ? "" : Number(e.target.value) }));

  const save = async () => {
    setSaving(true);
    try {
      const { has_vapi_api_key, webhook_url, vapi_api_key_last4, updated_at, ...rest } = s;
      const payload = { ...rest, dnc_numbers: dnc.split(/[\n,]/).map((x) => x.trim()).filter(Boolean),
        webhook_base_url: s.webhook_base_url || process.env.REACT_APP_BACKEND_URL };
      if (apiKey.trim()) payload.vapi_api_key = apiKey.trim();
      const { data } = await api.put("/settings", payload);
      load(data); setApiKey("");
      toast.success("Settings saved");
    } catch (e) {
      toast.error(errMsg(e));
      const { data } = await api.get("/settings");
      setS((p) => ({ ...p, call_mode: data.call_mode }));
    } finally { setSaving(false); }
  };

  const test = async () => {
    try {
      const { data } = await api.post("/settings/test-vapi");
      data.ok ? toast.success(`Vapi connected · ${data.number || "number"} (${data.provider || "provider"})`) : toast.error(`Vapi check failed (${data.http_status}): ${data.message}`);
    } catch (e) { toast.error(errMsg(e)); }
  };

  const rotate = async () => { const { data } = await api.post("/settings/rotate-webhook-token"); load(data); toast.success("Webhook token rotated"); };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-end justify-between gap-4 pb-2">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-blue-400">Admin · Supervisor</p>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-slate-100 sm:text-3xl">Provider & campaign defaults</h1>
        </div>
        <Button onClick={save} disabled={saving} className="gap-2" data-testid="settings-save-button"><Save className="h-4 w-4" />{saving ? "Saving…" : "Save settings"}</Button>
      </div>

      <Section title="Calling mode" desc="Simulation runs the full pipeline with mocked calls. Live places real calls through Vapi." testId="settings-mode-section">
        <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/70 p-4">
          <div>
            <div className="text-sm font-medium text-slate-200">{s.call_mode === "live" ? "Live calling (Vapi)" : "Simulation (mock calls)"}</div>
            <div className="text-xs text-slate-500">Live requires API key + Phone Number ID.</div>
          </div>
          <Switch checked={s.call_mode === "live"} onCheckedChange={(v) => set("call_mode")(v ? "live" : "simulation")} data-testid="settings-live-mode-switch" />
        </div>
      </Section>

      <Section title="Vapi credentials" desc="Stored encrypted server-side. Never returned to the browser." testId="settings-vapi-section">
        <Field label="Vapi private API key" hint={s.has_vapi_api_key ? `Saved key ending in ••••${s.vapi_api_key_last4}. Enter a new value to rotate.` : "No key saved yet."}>
          <div className="relative"><KeyRound className="absolute left-3 top-3 h-4 w-4 text-slate-500" />
            <Input type="password" className="pl-9 font-mono" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={s.has_vapi_api_key ? "••••••••••••" : "vapi private key"} data-testid="settings-vapi-api-key-input" /></div>
        </Field>
        <Field label="Phone Number ID" hint="Vapi phoneNumberId of an imported Twilio/Vonage/Telnyx number.">
          <Input className="font-mono" value={s.phone_number_id} onChange={set("phone_number_id")} data-testid="settings-phone-number-id-input" />
        </Field>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="LLM provider (Vapi)"><Input value={s.vapi_model_provider} onChange={set("vapi_model_provider")} data-testid="settings-vapi-model-provider-input" /></Field>
          <Field label="LLM model (Vapi)"><Input value={s.vapi_model} onChange={set("vapi_model")} data-testid="settings-vapi-model-input" /></Field>
        </div>
        <Field label="Webhook base URL" hint="Public URL Vapi can reach. Defaults to this app's backend URL.">
          <Input className="font-mono" value={s.webhook_base_url} placeholder={process.env.REACT_APP_BACKEND_URL} onChange={set("webhook_base_url")} data-testid="settings-webhook-base-input" />
        </Field>
        {s.webhook_url && (
          <div className="flex items-center gap-2 rounded-md border border-slate-800 bg-[#0B0F17] p-2.5">
            <code className="flex-1 truncate text-[11px] text-slate-400" data-testid="settings-webhook-url">{s.webhook_url}</code>
            <Button size="icon" variant="ghost" onClick={() => { navigator.clipboard?.writeText(s.webhook_url); toast.success("Copied"); }} data-testid="copy-webhook-url"><Copy className="h-4 w-4" /></Button>
            <Button size="icon" variant="ghost" onClick={rotate} data-testid="rotate-webhook-token"><RefreshCw className="h-4 w-4" /></Button>
          </div>
        )}
        <Button variant="outline" className="gap-2 border-slate-700" onClick={test} data-testid="settings-test-vapi-btn"><PlugZap className="h-4 w-4" />Test Vapi connection</Button>
      </Section>

      <Section title="Voice profiles" desc="Exactly three profiles: English, Bengali, Hindi. Each sets the voice (ElevenLabs or Azure Neural) and the transcriber so the agent speaks and understands that language." testId="settings-voices-section">
        <VoiceProfilesTable profiles={s.voice_profiles} onChange={set("voice_profiles")} />
        <div className="grid gap-4 md:grid-cols-4">
          <Field label="Default agent name" hint="Prefills new campaigns. Spoken as {{agent_name}}.">
            <Input value={s.default_agent_name} placeholder="e.g. Ria" onChange={set("default_agent_name")} data-testid="settings-default-agent-name-input" />
          </Field>
          <Field label="Default voice gender">
            <Select value={s.default_voice_gender} onValueChange={set("default_voice_gender")}>
              <SelectTrigger data-testid="settings-default-gender-select"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="female">Female</SelectItem><SelectItem value="male">Male</SelectItem></SelectContent>
            </Select>
          </Field>
          <Field label="Voice stability" hint="Lower = more expressive">
            <Input type="number" step="0.05" min="0" max="1" className="font-mono" value={s.voice_stability} onChange={num("voice_stability")} data-testid="settings-voice-stability-input" />
          </Field>
          <Field label="Voice style / emotion" hint="Higher = more emotional">
            <Input type="number" step="0.05" min="0" max="1" className="font-mono" value={s.voice_style} onChange={num("voice_style")} data-testid="settings-voice-style-input" />
          </Field>
        </div>
      </Section>

      <Section title="State → language rule" desc="Each contact's state/province picks the call language. States not listed use the fallback." testId="settings-state-rules-section">
        <StateRulesEditor rules={s.state_language_rules} onChange={set("state_language_rules")} />
        <Field label="Fallback language (all other states)"><FallbackLanguage value={s.fallback_language} onChange={set("fallback_language")} /></Field>
      </Section>

      <Section title="Script templates" desc="Intro and closing lines per language. Variables: {{agent_name}}, {{bank_name}}, {{customer_name}}." testId="settings-scripts-section">
        <ScriptsEditor templates={s.script_templates} onChange={set("script_templates")} />
      </Section>

      <Section title="Disposition buckets" desc="Eight canonical codes. The agent picks one per call using these rules; category feeds the export." testId="settings-dispositions-section">
        <DispositionsEditor items={s.dispositions} onChange={set("dispositions")} />
        <Field label="Bucket for unreached calls" hint="Used when the call never connects (no answer, voicemail, busy, failed). Call Status keeps the provider state.">
          <Select value={s.unreached_disposition} onValueChange={set("unreached_disposition")}>
            <SelectTrigger className="w-64" data-testid="settings-unreached-disposition-select"><SelectValue /></SelectTrigger>
            <SelectContent>{DISPOSITIONS.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}</SelectContent>
          </Select>
        </Field>
      </Section>

      <Section title="AI agent prompt & emotion" desc="Default style notes for new campaigns, plus the tone rules every call follows. Hard RPI rules always take precedence." testId="settings-prompt-section">
        <Textarea rows={3} value={s.default_prompt} onChange={set("default_prompt")} data-testid="settings-prompt-textarea" />
        <Field label="Emotion & tone guidelines" hint="Warm by default, condolences on death, calm & apologetic when hostile, cheerful when friendly.">
          <Textarea rows={7} value={s.emotion_guidelines} onChange={set("emotion_guidelines")} data-testid="settings-emotion-textarea" />
        </Field>
        <Field label="RPC confirmation confidence threshold" hint="If the classifier picks RPC_CONFIRMED below this confidence, the call goes to the unreached bucket and is flagged for review.">
          <Input type="number" step="0.05" min="0.5" max="1" className="w-32 font-mono" value={s.confirm_confidence_threshold} onChange={num("confirm_confidence_threshold")} data-testid="settings-confidence-input" />
        </Field>
      </Section>

      <Section title="Retry & throughput" desc="Applies to manual retries and the outbound queue." testId="settings-retry-section">
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Max retries per contact"><Input type="number" className="font-mono" value={s.max_retries} onChange={num("max_retries")} data-testid="settings-max-retries-input" /></Field>
          <Field label="Max concurrent calls"><Input type="number" className="font-mono" value={s.max_concurrent_calls} onChange={num("max_concurrent_calls")} data-testid="settings-max-concurrent-input" /></Field>
          <Field label="Max call duration (s)"><Input type="number" className="font-mono" value={s.max_call_duration_seconds} onChange={num("max_call_duration_seconds")} data-testid="settings-max-duration-input" /></Field>
        </div>
      </Section>

      <Section title="Compliance" desc="Do-Not-Call suppression and calling window (TRAI / DND-style). Applied at import and dial time." testId="settings-compliance-section">
        <Field label="Default phone region" hint="ISO country code used to parse numbers without a +country prefix.">
          <Input className="w-32 font-mono uppercase" value={s.default_region} onChange={set("default_region")} data-testid="settings-region-input" />
        </Field>
        <Field label="Do-Not-Call numbers (E.164, one per line)">
          <Textarea rows={4} className="font-mono text-xs" value={dnc} onChange={(e) => setDnc(e.target.value)} placeholder="+14165550100" data-testid="settings-dnc-textarea" />
        </Field>
        <div className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/70 p-4">
          <div className="text-sm text-slate-200">Enforce calling hours</div>
          <Switch checked={s.enforce_calling_hours} onCheckedChange={set("enforce_calling_hours")} data-testid="settings-calling-hours-switch" />
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <Field label="Start hour"><Input type="number" className="font-mono" value={s.calling_hours_start} onChange={num("calling_hours_start")} data-testid="settings-hours-start-input" /></Field>
          <Field label="End hour"><Input type="number" className="font-mono" value={s.calling_hours_end} onChange={num("calling_hours_end")} data-testid="settings-hours-end-input" /></Field>
          <Field label="Timezone"><Input className="font-mono" value={s.calling_timezone} onChange={set("calling_timezone")} data-testid="settings-timezone-input" /></Field>
        </div>
      </Section>
    </div>
  );
}
