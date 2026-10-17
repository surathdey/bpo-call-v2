import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Download, Pause, Play, RotateCcw, Search, SlidersHorizontal, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, DISPOSITIONS, errMsg, LANGUAGES, usePoll } from "@/lib/api";
import { KpiGrid } from "@/components/rpi/KpiGrid";
import { StatusBadge, dispositionLabel } from "@/components/rpi/Badges";
import { ContactsTable } from "@/components/rpi/ContactsTable";
import { UploadDialog } from "@/components/rpi/UploadDialog";
import { CallDetailSheet } from "@/components/rpi/CallDetailSheet";
import { CampaignFormDialog } from "@/components/rpi/CampaignFormDialog";
import { cn } from "@/lib/utils";

const ALL = "ALL";

const FilterTabs = ({ value, onChange, stats }) => (
  <div className="flex flex-wrap gap-1" data-testid="filter-disposition-tabs">
    {[ALL, ...DISPOSITIONS, "NONE"].map((d) => (
      <button key={d} onClick={() => onChange(d === ALL ? "" : d)} data-testid={`filter-disposition-${d.replace(/\s+/g, "_")}`}
        className={cn("rounded-md border px-2.5 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors",
          (value || ALL) === d ? "border-blue-500/50 bg-blue-500/10 text-blue-300" : "border-slate-800 text-slate-400 hover:text-slate-200")}>
        {d === ALL ? "All" : d === "NONE" ? "Not dialed" : dispositionLabel(d)}
        {stats && d !== ALL && d !== "NONE" && <span className="ml-1.5 text-slate-500">{stats[d]}</span>}
      </button>
    ))}
  </div>
);

const ScriptPanel = ({ c }) => (
  <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4 text-xs" data-testid="script-panel">
    <div className="mb-2 font-mono text-[10px] uppercase tracking-widest text-slate-500">
      Intro script · agent <span className="text-blue-300" data-testid="script-agent-name">{c.agent_name || "NOT SET"}</span> · {c.voice_gender} voice ·
      rules: {c.state_rules.map((r) => `${r.state} → ${r.language}`).join(", ") || "none"} · else {c.fallback_language}
    </div>
    <div className="grid gap-3 md:grid-cols-3">
      {Object.entries(c.scripts).map(([lang, s]) => (
        <div key={lang} data-testid={`script-${lang}`}>
          <div className="mb-1 font-mono text-[10px] text-slate-500">{s.label} · {s.voice_name || s.voice_id || "no voice id"}</div>
          <p className="text-slate-300">{s.opening}</p>
        </div>
      ))}
    </div>
    {!c.agent_name && <p className="mt-2 text-amber-400" data-testid="agent-name-missing">Set an agent name before launching.</p>}
    {c.prompt_flags?.length > 0 && (
      <p className="mt-2 text-amber-400" data-testid="prompt-flags">Guardrail stripped {c.prompt_flags.length} prompt line(s): “{c.prompt_flags[0]}”</p>
    )}
  </div>
);

export default function CampaignDetailPage() {
  const { id } = useParams();
  const [filter, setFilter] = useState("");
  const [status, setStatus] = useState("");
  const [language, setLanguage] = useState("");
  const [q, setQ] = useState("");
  const [review, setReview] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [upload, setUpload] = useState(false);
  const [edit, setEdit] = useState(false);
  const [openContact, setOpenContact] = useState(null);
  const [busy, setBusy] = useState("");

  const { data: c, reload: reloadC } = usePoll(() => api.get(`/campaigns/${id}`).then((r) => r.data), 3000);
  const params = useMemo(() => ({ disposition: filter || undefined, status: status || undefined,
    language: language || undefined, q: q || undefined, review: review || undefined }), [filter, status, language, q, review]);
  const { data: rows, reload } = usePoll(() => api.get(`/campaigns/${id}/contacts`, { params }).then((r) => r.data), 3000);
  useEffect(() => { reload(); }, [params, reload]);

  const act = async (name, fn, ok) => {
    setBusy(name);
    try {
      const res = await fn();
      toast.success(typeof ok === "function" ? ok(res.data) : ok);
      reloadC(); reload();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy("");
    }
  };

  const exportCsv = async () => {
    try {
      const res = await api.get(`/campaigns/${id}/export`, { params: { disposition: filter && filter !== "NONE" ? filter : undefined }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url; a.download = `rpi_${c?.name || id}_${filter || "all"}.csv`.replace(/\s+/g, "_"); a.click();
      URL.revokeObjectURL(url);
      toast.success("Export downloaded");
    } catch (e) { toast.error(errMsg(e)); }
  };

  const retryBody = selected.size ? { contact_ids: [...selected] } : {};
  const toggle = (cid) => setSelected((s) => { const n = new Set(s); n.has(cid) ? n.delete(cid) : n.add(cid); return n; });
  const toggleAll = () => setSelected((s) => (rows?.every((r) => s.has(r.id)) ? new Set() : new Set(rows?.map((r) => r.id))));

  if (!c) return <div className="text-sm text-slate-500" data-testid="campaign-loading">Loading campaign…</div>;

  return (
    <div className="mx-auto max-w-[1500px] space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/rpi/campaigns" className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-widest text-slate-500 hover:text-slate-300" data-testid="back-to-campaigns">
            <ArrowLeft className="h-3 w-3" /> Campaigns</Link>
          <div className="mt-1 flex items-center gap-3">
            <h1 className="font-display text-2xl font-bold tracking-tight text-slate-100 sm:text-3xl" data-testid="campaign-title">{c.name}</h1>
            <StatusBadge value={c.status} testId="campaign-status-badge" />
          </div>
          {c.description && <p className="mt-1 text-sm text-slate-400">{c.description}</p>}
        </div>
        <Button variant="outline" className="gap-2 border-slate-700" onClick={() => setEdit(true)} data-testid="edit-campaign-settings-btn">
          <SlidersHorizontal className="h-4 w-4" /> Voice & script</Button>
      </div>

      <div className="sticky top-14 z-20 -mx-1 flex flex-wrap items-center gap-2 rounded-lg border border-slate-800 bg-[#0d121c]/95 p-2 backdrop-blur-xl" data-testid="ops-bar">
        <Button size="sm" variant="secondary" className="gap-2" onClick={() => setUpload(true)} data-testid="btn-upload-csv"><Upload className="h-4 w-4" />Upload CSV</Button>
        <div className="mx-1 h-5 w-px bg-slate-800" />
        <Button size="sm" className="gap-2 bg-emerald-600 hover:bg-emerald-500" disabled={c.status === "running" || busy === "launch"} data-testid="btn-launch-campaign"
          onClick={() => act("launch", () => api.post(`/campaigns/${id}/launch`), `Campaign launched (${c.call_mode})`)}>
          <Play className="h-4 w-4" />{c.status === "paused" ? "Resume" : "Launch"}</Button>
        <Button size="sm" variant="secondary" className="gap-2" disabled={c.status !== "running" || busy === "pause"} data-testid="btn-pause-campaign"
          onClick={() => act("pause", () => api.post(`/campaigns/${id}/pause`), "Queue paused")}><Pause className="h-4 w-4" />Pause</Button>
        <Button size="sm" variant="secondary" className="gap-2" disabled={busy === "retry"} data-testid="btn-retry-failed"
          onClick={() => act("retry", () => api.post(`/campaigns/${id}/retry`, retryBody),
            (d) => `Re-queued ${d.requeued}${d.skipped_retry_limit ? ` · ${d.skipped_retry_limit} at retry limit` : ""}`).then(() => setSelected(new Set()))}>
          <RotateCcw className="h-4 w-4" />{selected.size ? `Retry selected (${selected.size})` : "Retry unreached"}</Button>
        <Button size="sm" variant="secondary" className="gap-2" onClick={exportCsv} data-testid="btn-export-csv"><Download className="h-4 w-4" />Export{filter && filter !== "NONE" ? ` ${dispositionLabel(filter)}` : ""}</Button>
        <span className="ml-auto pr-2 font-mono text-[11px] text-slate-500" data-testid="queue-summary">
          {c.stats.queued} queued · {c.stats.calling} calling · {c.stats.completed} done</span>
      </div>

      <KpiGrid stats={c.stats} filter={filter} onFilter={setFilter} />
      <ScriptPanel c={c} />

      <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/70">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-800 p-3">
          <FilterTabs value={filter} onChange={setFilter} stats={c.stats} />
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <button onClick={() => setReview((v) => !v)} data-testid="filter-review-toggle"
              className={cn("rounded-md border px-2.5 py-1 font-mono text-[11px] uppercase", review ? "border-amber-500/50 text-amber-400" : "border-slate-800 text-slate-400")}>
              Needs review {c.stats.review_required}</button>
            <Select value={status || ALL} onValueChange={(v) => setStatus(v === ALL ? "" : v)}>
              <SelectTrigger className="h-8 w-32 text-xs" data-testid="filter-status-select"><SelectValue /></SelectTrigger>
              <SelectContent>{[ALL, "pending", "queued", "calling", "completed"].map((s) => <SelectItem key={s} value={s}>{s === ALL ? "Any state" : s}</SelectItem>)}</SelectContent>
            </Select>
            <Select value={language || ALL} onValueChange={(v) => setLanguage(v === ALL ? "" : v)}>
              <SelectTrigger className="h-8 w-32 text-xs" data-testid="filter-language-select"><SelectValue /></SelectTrigger>
              <SelectContent>{[{ code: ALL, label: "Any language" }, ...LANGUAGES].map((l) => <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>)}</SelectContent>
            </Select>
            <div className="relative">
              <Search className="absolute left-2 top-2 h-4 w-4 text-slate-500" />
              <Input className="h-8 w-52 pl-8 text-xs" placeholder="Name, phone, bank, state" value={q} onChange={(e) => setQ(e.target.value)} data-testid="table-search-input" />
            </div>
          </div>
        </div>
        <ContactsTable rows={rows || []} selected={selected} onToggle={toggle} onToggleAll={toggleAll} onOpen={setOpenContact} />
      </div>

      <UploadDialog open={upload} onOpenChange={setUpload} campaignId={id} onImported={() => { reloadC(); reload(); }} />
      <CampaignFormDialog open={edit} onOpenChange={setEdit} campaign={c} onSaved={() => reloadC()} />
      <CallDetailSheet contactId={openContact} onClose={() => setOpenContact(null)} />
    </div>
  );
}
