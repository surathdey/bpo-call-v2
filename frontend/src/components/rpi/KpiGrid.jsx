import { cn } from "@/lib/utils";
import { DISPOSITIONS } from "@/lib/api";
import { dispositionLabel, dispositionText } from "@/components/rpi/Badges";

const slug = (d) => d.toLowerCase().replace(/\s+/g, "-");

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
  const done = DISPOSITIONS.reduce((n, d) => n + (stats[d] || 0), 0);
  const pct = (n) => (done ? `${Math.round((n / done) * 100)}% of dialed` : "—");
  const f = (k) => (onFilter ? () => onFilter(filter === k ? "" : k) : undefined);
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
      <Stat testId="kpi-total-contacts" label="Contacts" value={stats.total}
        sub={`${stats.pending + stats.queued} waiting · ${stats.calling} live`} />
      <Stat testId="kpi-rpi-rate" label="RPC rate" value={`${stats.rpi_rate}%`} accent="text-blue-400"
        sub={`avg ${stats.avg_duration}s · ${stats.review_required} need review`} />
      {DISPOSITIONS.map((d) => (
        <Stat key={d} testId={`kpi-${slug(d)}`} label={dispositionLabel(d)} value={stats[d] || 0} accent={dispositionText(d)}
          sub={pct(stats[d] || 0)} onClick={f(d)} active={filter === d} />
      ))}
    </div>
  );
};
