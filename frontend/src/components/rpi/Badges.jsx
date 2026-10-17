import { cn } from "@/lib/utils";

const DISPO = {
  RPC_CONFIRMED: { label: "RPC Confirmed", cls: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400", dot: "bg-emerald-500", text: "text-emerald-400" },
  CPC_CONFIRMED: { label: "CPC Confirmed", cls: "bg-teal-500/10 border-teal-500/30 text-teal-300", dot: "bg-teal-400", text: "text-teal-300" },
  CALLBACK_REQUESTED: { label: "Callback", cls: "bg-sky-500/10 border-sky-500/30 text-sky-300", dot: "bg-sky-400", text: "text-sky-300" },
  FINAL_DENIAL: { label: "Final Denial", cls: "bg-rose-500/10 border-rose-500/30 text-rose-400", dot: "bg-rose-500", text: "text-rose-400" },
  "Final Denial Closing": { label: "Final Denial Closing", cls: "bg-slate-500/10 border-slate-500/30 text-slate-300", dot: "bg-slate-400", text: "text-slate-300" },
  HOSTILE: { label: "Hostile", cls: "bg-orange-500/10 border-orange-500/30 text-orange-400", dot: "bg-orange-500", text: "text-orange-400" },
  DECEASED_CASE: { label: "Deceased", cls: "bg-violet-500/10 border-violet-500/30 text-violet-300", dot: "bg-violet-400", text: "text-violet-300" },
  DNC_ESCALATION: { label: "DNC Escalation", cls: "bg-amber-500/10 border-amber-500/30 text-amber-400", dot: "bg-amber-500", text: "text-amber-400" },
};

export const dispositionText = (v) => DISPO[v]?.text || "text-slate-300";

const STATUS = {
  pending: { label: "Pending", cls: "bg-slate-500/10 border-slate-600/40 text-slate-400", dot: "bg-slate-500" },
  queued: { label: "Queued", cls: "bg-indigo-500/10 border-indigo-500/30 text-indigo-300", dot: "bg-indigo-400" },
  calling: { label: "Calling", cls: "bg-blue-500/10 border-blue-500/30 text-blue-400", dot: "bg-blue-500 animate-pulse" },
  completed: { label: "Completed", cls: "bg-slate-500/10 border-slate-600/40 text-slate-300", dot: "bg-slate-300" },
  draft: { label: "Draft", cls: "bg-slate-500/10 border-slate-600/40 text-slate-400", dot: "bg-slate-500" },
  running: { label: "Running", cls: "bg-blue-500/10 border-blue-500/30 text-blue-400", dot: "bg-blue-500 animate-pulse" },
  paused: { label: "Paused", cls: "bg-amber-500/10 border-amber-500/30 text-amber-400", dot: "bg-amber-500" },
};

const Pill = ({ meta, testId, mono = true }) => (
  <span data-testid={testId}
    className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-2 py-0.5 text-[11px] font-medium",
      mono && "font-mono uppercase tracking-wide", meta.cls)}>
    <span className={cn("h-1.5 w-1.5 rounded-full", meta.dot)} />
    {meta.label}
  </span>
);

export const DispositionBadge = ({ value, testId }) =>
  value ? <Pill meta={DISPO[value] || { ...DISPO["Final Denial Closing"], label: value }} testId={testId} />
    : <span className="font-mono text-xs text-slate-600" data-testid={testId}>—</span>;

export const StatusBadge = ({ value, testId }) => <Pill meta={STATUS[value] || STATUS.pending} testId={testId} />;

export const dispositionLabel = (v) => DISPO[v]?.label || v;
