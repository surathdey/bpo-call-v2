import { Bot, Copy, Mic, User } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api, fmtTime, usePoll } from "@/lib/api";
import { DispositionBadge, StatusBadge } from "@/components/rpi/Badges";

const Row = ({ k, v, mono, testId }) => (
  <div className="flex justify-between gap-4 py-1.5 text-xs">
    <span className="text-slate-500">{k}</span>
    <span className={mono ? "font-mono text-slate-300" : "text-slate-300"} data-testid={testId}>{v ?? "—"}</span>
  </div>
);

const Transcript = ({ turns }) => {
  if (!turns?.length) return <p className="text-xs text-slate-500" data-testid="call-transcript-empty">No transcript (no speech captured).</p>;
  return (
    <div className="space-y-2" data-testid="call-transcript-list">
      {turns.map((t, i) => {
        const agent = t.role === "agent";
        return (
          <div key={i} className={`flex gap-2 ${agent ? "" : "flex-row-reverse"}`}>
            <div className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded ${agent ? "bg-blue-500/15 text-blue-300" : "bg-slate-700/60 text-slate-300"}`}>
              {agent ? <Bot className="h-3.5 w-3.5" /> : <User className="h-3.5 w-3.5" />}
            </div>
            <div className={`max-w-[80%] rounded-md border px-3 py-2 text-xs leading-relaxed ${agent ? "border-blue-500/20 bg-blue-500/5" : "border-slate-700 bg-slate-800/50"}`}>
              <div className="mb-0.5 font-mono text-[10px] uppercase tracking-wider text-slate-500">{agent ? "AI agent" : "Callee"}{t.t != null && ` · ${Number(t.t).toFixed(1)}s`}</div>
              {t.text}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const Attempt = ({ a }) => (
  <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4" data-testid={`attempt-${a.id}`}>
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <span className="font-mono text-xs text-slate-400">Attempt #{a.attempt_number} · {a.mode}</span>
      <div className="flex items-center gap-2">
        {a.review_required && <span className="rounded border border-amber-500/40 px-1.5 py-0.5 font-mono text-[10px] uppercase text-amber-400" data-testid="attempt-review-flag">Needs review</span>}
        <DispositionBadge value={a.disposition} testId="attempt-disposition" />
      </div>
    </div>
    <div className="divide-y divide-slate-800/70">
      <Row k="Provider call ID" mono testId="vapi-call-id-badge" v={a.provider_call_id ? (
        <button className="inline-flex items-center gap-1 hover:text-blue-300" onClick={() => { navigator.clipboard?.writeText(a.provider_call_id); toast.success("Copied"); }}>
          {a.provider_call_id.slice(0, 18)}… <Copy className="h-3 w-3" /></button>) : a.mode === "simulation" ? "simulated" : "—"} />
      <Row k="Provider status" mono v={a.provider_status} testId="attempt-provider-status" />
      <Row k="Ended reason" mono v={a.ended_reason} testId="attempt-ended-reason" />
      <Row k="Created" v={fmtTime(a.created_at)} />
      <Row k="Started" v={fmtTime(a.started_at)} />
      <Row k="Ended" v={fmtTime(a.ended_at)} />
      <Row k="Duration" mono v={a.duration_seconds != null ? `${a.duration_seconds}s` : "—"} />
      <Row k="Voice profile" mono v={a.voice_id} />
      <Row k="Callbacks received" mono v={a.webhook_events} />
    </div>
    {a.classification && (
      <div className="mt-3 rounded-md border border-slate-800 bg-[#0B0F17] p-3 text-xs" data-testid="attempt-classification">
        <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-slate-500">
          Classifier: {a.classification.source} · confidence {Math.round(a.classification.confidence * 100)}%
          {a.classification.raw_disposition !== a.disposition && ` · raw ${a.classification.raw_disposition}`}
        </div>
        <p className="text-slate-300">{a.classification.reasoning}</p>
      </div>
    )}
    {a.error && <p className="mt-2 font-mono text-[11px] text-rose-400">{a.error}</p>}
    <div className="mt-4">
      <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-slate-500"><Mic className="h-3 w-3" /> Recording</div>
      {a.recording_url ? <audio controls src={a.recording_url} className="h-9 w-full" data-testid="call-recording-audio" />
        : <p className="text-xs text-slate-500" data-testid="call-recording-empty">No recording available{a.mode === "simulation" ? " (simulated call)" : ""}.</p>}
    </div>
    <div className="mt-4">
      <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-slate-500">Transcript</div>
      <Transcript turns={a.transcript} />
    </div>
  </div>
);

export const CallDetailSheet = ({ contactId, onClose }) => {
  const { data } = usePoll(() => (contactId ? api.get(`/contacts/${contactId}`).then((r) => r.data) : null), contactId ? 3000 : 0);
  const c = data?.contact;
  return (
    <Sheet open={Boolean(contactId)} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-full border-slate-800 bg-[#0d121c] p-0 sm:max-w-xl" data-testid="call-detail-drawer">
        <SheetHeader className="border-b border-slate-800 p-6">
          <SheetTitle className="font-display text-slate-100" data-testid="drawer-contact-name">{c?.name || "Loading…"}</SheetTitle>
          <SheetDescription className="font-mono text-xs">
            {c?.phone} {c?.customer_id && `· ${c.customer_id}`} {c && `· ${c.language}`}
          </SheetDescription>
          {c && <div className="flex gap-2 pt-1"><StatusBadge value={c.status} testId="drawer-contact-status" /><DispositionBadge value={c.disposition} testId="drawer-contact-disposition" /></div>}
        </SheetHeader>
        <ScrollArea className="h-[calc(100vh-130px)]">
          <div className="space-y-4 p-6">
            {c?.warnings?.length > 0 && <p className="text-xs text-amber-400">Import warnings: {c.warnings.join("; ")}</p>}
            {data?.attempts?.length ? data.attempts.map((a) => <Attempt key={a.id} a={a} />)
              : <p className="text-sm text-slate-500" data-testid="drawer-no-attempts">No call attempts yet.</p>}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
};
