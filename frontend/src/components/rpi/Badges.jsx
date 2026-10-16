import { cn } from "@/lib/utils";

const DISPO = {
  RPI_CONFIRMED: { label: "RPI Confirmed", cls: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400", dot: "bg-emerald-500" },
  WRONG_PARTY: { label: "Wrong Party", cls: "bg-rose-500/10 border-rose-500/30 text-rose-400", dot: "bg-rose-500" },
  NO_ANSWER_VOICEMAIL: { label: "No Answer / VM", cls: "bg-amber-500/10 border-amber-500/30 text-amber-400", dot: "bg-amber-500" },
  FAILED_NUMBER: { label: "Failed Number", cls: "bg-slate-500/10 border-slate-500/30 text-slate-400", dot: "bg-slate-500" },
};

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
  value ? <Pill meta={DISPO[value] || { ...DISPO.FAILED_NUMBER, label: value }} testId={testId} />
    : <span className="font-mono text-xs text-slate-600" data-testid={testId}>—</span>;

export const StatusBadge = ({ value, testId }) => <Pill meta={STATUS[value] || STATUS.pending} testId={testId} />;

export const dispositionLabel = (v) => DISPO[v]?.label || v;
