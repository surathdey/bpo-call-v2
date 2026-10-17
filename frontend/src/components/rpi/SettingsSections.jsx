import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LANGUAGES, SCRIPT_KEYS } from "@/lib/api";
import { dispositionLabel } from "@/components/rpi/Badges";

const TH = ({ children }) => <th className="p-2.5 text-left font-mono text-[10px] uppercase tracking-wider text-slate-500">{children}</th>;
const cell = "h-8 font-mono text-xs";

const LangSelect = ({ value, onChange, testId }) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger className="h-8 text-xs" data-testid={testId}><SelectValue /></SelectTrigger>
    <SelectContent>{LANGUAGES.map((l) => <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>)}</SelectContent>
  </Select>
);

export const VoiceProfilesTable = ({ profiles, onChange }) => {
  const set = (i, k, v) => onChange(profiles.map((p, j) => (j === i ? { ...p, [k]: v } : p)));
  const cols = [["female_voice_id", "Female voice ID"], ["female_voice_name", "Female voice name"],
    ["male_voice_id", "Male voice ID"], ["male_voice_name", "Male voice name"], ["tts_model", "TTS model"],
    ["stt_provider", "STT provider"], ["stt_model", "STT model"], ["stt_language", "STT lang"]];
  return (
    <div className="thin-scroll overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm" data-testid="voice-profiles-table">
        <thead className="bg-slate-900/80"><tr><TH>Profile</TH><TH>TTS provider</TH>{cols.map(([, l]) => <TH key={l}>{l}</TH>)}</tr></thead>
        <tbody>
          {profiles.map((p, i) => (
            <tr key={p.language} className="border-t border-slate-800">
              <td className="whitespace-nowrap p-2.5 text-xs font-medium text-slate-200">{p.label} <span className="font-mono text-slate-500">{p.language}</span></td>
              <td className="p-1.5">
                <Select value={p.tts_provider} onValueChange={(v) => set(i, "tts_provider", v)}>
                  <SelectTrigger className="h-8 min-w-[110px] text-xs" data-testid={`voice-${p.language}-tts_provider`}><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="11labs">ElevenLabs</SelectItem><SelectItem value="azure">Azure Neural</SelectItem></SelectContent>
                </Select>
              </td>
              {cols.map(([k]) => (
                <td key={k} className="p-1.5"><Input className={`${cell} ${k.includes("voice") ? "min-w-[200px]" : k === "tts_model" ? "min-w-[170px]" : "min-w-[90px]"}`} value={p[k] || ""} onChange={(e) => set(i, k, e.target.value)}
                  data-testid={`voice-${p.language}-${k}`} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const StateRulesEditor = ({ rules, onChange }) => {
  const set = (i, k, v) => onChange(rules.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  return (
    <div className="space-y-2" data-testid="state-rules-editor">
      {rules.map((r, i) => (
        <div key={i} className="grid grid-cols-[1fr_180px_40px] gap-2" data-testid={`state-rule-row-${i}`}>
          <Input className="h-8 text-xs" value={r.state} placeholder="State / province" onChange={(e) => set(i, "state", e.target.value)} data-testid={`state-rule-state-${i}`} />
          <LangSelect value={r.language} onChange={(v) => set(i, "language", v)} testId={`state-rule-language-${i}`} />
          <Button size="icon" variant="ghost" className="h-8 w-8 text-slate-500 hover:text-rose-400" onClick={() => onChange(rules.filter((_, j) => j !== i))} data-testid={`state-rule-delete-${i}`}><Trash2 className="h-4 w-4" /></Button>
        </div>
      ))}
      <Button size="sm" variant="outline" className="gap-1.5 border-slate-700" onClick={() => onChange([...rules, { state: "", language: "hi-IN" }])} data-testid="state-rule-add">
        <Plus className="h-3.5 w-3.5" />Add rule</Button>
    </div>
  );
};

export const FallbackLanguage = ({ value, onChange }) => <div className="w-48"><LangSelect value={value} onChange={onChange} testId="settings-fallback-language-select" /></div>;

export const PronunciationEditor = ({ items, onChange, onPreview }) => {
  const set = (i, k, v) => onChange(items.map((o, j) => (j === i ? { ...o, [k]: v } : o)));
  return (
    <div className="space-y-2" data-testid="pronunciation-editor">
      {items.map((o, i) => (
        <div key={i} className="grid grid-cols-[1fr_150px_1fr_40px] gap-2" data-testid={`pron-row-${i}`}>
          <Input className="h-8 text-xs" value={o.name} placeholder="Name or word as in CSV (e.g. Surath Dey / Dey)" onChange={(e) => set(i, "name", e.target.value)} data-testid={`pron-name-${i}`} />
          <LangSelect value={o.language} onChange={(v) => set(i, "language", v)} testId={`pron-language-${i}`} />
          <Input className="h-8 text-xs" value={o.spoken} placeholder="How to say it (e.g. সুরথ দে)" onChange={(e) => set(i, "spoken", e.target.value)} data-testid={`pron-spoken-${i}`} />
          <Button size="icon" variant="ghost" className="h-8 w-8 text-slate-500 hover:text-rose-400" onClick={() => onChange(items.filter((_, j) => j !== i))} data-testid={`pron-delete-${i}`}><Trash2 className="h-4 w-4" /></Button>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" className="gap-1.5 border-slate-700" onClick={() => onChange([...items, { name: "", language: "bn-IN", spoken: "" }])} data-testid="pron-add">
          <Plus className="h-3.5 w-3.5" />Add pronunciation</Button>
        {onPreview}
      </div>
    </div>
  );
};

export const DispositionsEditor = ({ items, onChange }) => {
  const set = (i, k, v) => onChange(items.map((d, j) => (j === i ? { ...d, [k]: v } : d)));
  return (
    <div className="overflow-hidden rounded-lg border border-slate-800">
      <table className="w-full text-sm" data-testid="dispositions-table">
        <thead className="bg-slate-900/80"><tr><TH>Code</TH><TH>Category</TH><TH>Rule (agent + classifier)</TH><TH>Closing line</TH></tr></thead>
        <tbody>
          {items.map((d, i) => (
            <tr key={d.code} className="border-t border-slate-800 align-top">
              <td className="whitespace-nowrap p-2.5 font-mono text-[11px] text-slate-300" data-testid={`disposition-code-${i}`}>{d.code}<div className="text-[10px] text-slate-500">{d.label || dispositionLabel(d.code)}</div></td>
              <td className="p-1.5"><Input className="h-8 min-w-[130px] text-xs" value={d.category} onChange={(e) => set(i, "category", e.target.value)} data-testid={`disposition-category-${i}`} /></td>
              <td className="w-1/2 p-1.5"><Textarea rows={2} className="min-h-0 text-xs" value={d.description} onChange={(e) => set(i, "description", e.target.value)} data-testid={`disposition-description-${i}`} /></td>
              <td className="p-1.5">
                <Select value={d.close} onValueChange={(v) => set(i, "close", v)}>
                  <SelectTrigger className="h-8 min-w-[140px] font-mono text-[11px]" data-testid={`disposition-close-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>{SCRIPT_KEYS.filter((k) => k.endsWith("_close")).map((k) => <SelectItem key={k} value={k}>{k}</SelectItem>)}</SelectContent>
                </Select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export const ScriptsEditor = ({ templates, onChange }) => {
  const set = (lang, k, v) => onChange({ ...templates, [lang]: { ...(templates[lang] || {}), [k]: v } });
  return (
    <Tabs defaultValue="hi-IN" data-testid="scripts-editor">
      <TabsList>{LANGUAGES.map((l) => <TabsTrigger key={l.code} value={l.code} data-testid={`scripts-tab-${l.code}`}>{l.label}</TabsTrigger>)}</TabsList>
      {LANGUAGES.map((l) => (
        <TabsContent key={l.code} value={l.code} className="space-y-3">
          {SCRIPT_KEYS.map((k) => (
            <div key={k} className="space-y-1">
              <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500">{k}</div>
              <Textarea rows={2} className="text-sm" value={templates[l.code]?.[k] || ""} onChange={(e) => set(l.code, k, e.target.value)} data-testid={`script-${l.code}-${k}`} />
            </div>
          ))}
        </TabsContent>
      ))}
    </Tabs>
  );
};
