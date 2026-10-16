import { cn } from "@/lib/utils";

const Stat = ({ label, value, sub, accent, testId, onClick, active }) => (
  <button type="button" onClick={onClick} data-testid={testId} disabled={!onClick}
    className={cn("rise group flex flex-col items-start rounded-lg border bg-slate-900/80 p-4 text-left transition-colors",
      onClick && "hover:border-slate-600", active ? "border-blue-500/60" : "border-slate-800")}>
    <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{label}</span>
    <span className={cn("mt-2 font-mono text-2xl font-bold tracking-tight sm:text-3xl", accent || "text-slate-100")}>{value}</span>
    {sub && <span className="mt-1 text-xs text-slate-500">{sub}</span>}
  </button>
);

export const KpiGrid = ({ stats, filter, onFilter }) => {
  if (!stats) return null;
  const done = stats.RPI_CONFIRMED + stats.WRONG_PARTY + stats.NO_ANSWER_VOICEMAIL + stats.FAILED_NUMBER;
  const pct = (n) => (done ? `${Math.round((n / done) * 100)}% of dialed` : "—");
  const f = (k) => (onFilter ? () => onFilter(filter === k ? "" : k) : undefined);
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <Stat testId="kpi-total-contacts" label="Contacts" value={stats.total}
        sub={`${stats.pending + stats.queued} waiting · ${stats.calling} live`} />
      <Stat testId="kpi-rpi-rate" label="RPI rate" value={`${stats.rpi_rate}%`} accent="text-blue-400"
        sub={`avg ${stats.avg_duration}s · ${stats.review_required} need review`} />
      <Stat testId="kpi-rpi-confirmed" label="RPI Confirmed" value={stats.RPI_CONFIRMED} accent="text-emerald-400"
        sub={pct(stats.RPI_CONFIRMED)} onClick={f("RPI_CONFIRMED")} active={filter === "RPI_CONFIRMED"} />
      <Stat testId="kpi-wrong-party" label="Wrong Party" value={stats.WRONG_PARTY} accent="text-rose-400"
        sub={pct(stats.WRONG_PARTY)} onClick={f("WRONG_PARTY")} active={filter === "WRONG_PARTY"} />
      <Stat testId="kpi-voicemail" label="No Answer / VM" value={stats.NO_ANSWER_VOICEMAIL} accent="text-amber-400"
        sub={pct(stats.NO_ANSWER_VOICEMAIL)} onClick={f("NO_ANSWER_VOICEMAIL")} active={filter === "NO_ANSWER_VOICEMAIL"} />
      <Stat testId="kpi-failed" label="Failed Number" value={stats.FAILED_NUMBER} accent="text-slate-300"
        sub={pct(stats.FAILED_NUMBER)} onClick={f("FAILED_NUMBER")} active={filter === "FAILED_NUMBER"} />
    </div>
  );
};
