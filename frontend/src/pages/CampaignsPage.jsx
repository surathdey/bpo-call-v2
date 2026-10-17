import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, fmtTime, usePoll } from "@/lib/api";
import { KpiGrid } from "@/components/rpi/KpiGrid";
import { StatusBadge, dispositionLabel, dispositionText } from "@/components/rpi/Badges";
import { CampaignFormDialog } from "@/components/rpi/CampaignFormDialog";
import { DISPOSITIONS } from "@/lib/api";

const BAR_COLORS = { RPC_CONFIRMED: "bg-emerald-500", CPC_CONFIRMED: "bg-teal-400", CALLBACK_REQUESTED: "bg-sky-400",
  FINAL_DENIAL: "bg-rose-500", "Final Denial Closing": "bg-slate-400", HOSTILE: "bg-orange-500", DECEASED_CASE: "bg-violet-400",
  DNC_ESCALATION: "bg-amber-500" };

const Bar = ({ s }) => {
  const total = s.total || 1;
  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
      {DISPOSITIONS.map((k) => <div key={k} className={BAR_COLORS[k]} style={{ width: `${((s[k] || 0) / total) * 100}%` }} />)}
    </div>
  );
};

const BucketCounts = ({ s, cid }) => (
  <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1" data-testid={`campaign-bucket-counts-${cid}`}>
    {DISPOSITIONS.map((d) => (
      <span key={d} className="font-mono text-[10px] uppercase tracking-wide text-slate-500">
        {dispositionLabel(d)} <span className={dispositionText(d)}>{s[d] || 0}</span>
      </span>
    ))}
  </div>
);

export default function CampaignsPage() {
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const { data: campaigns, loading } = usePoll(() => api.get("/campaigns").then((r) => r.data), 5000);
  const { data: dash } = usePoll(() => api.get("/dashboard").then((r) => r.data), 5000);

  return (
    <div className="mx-auto max-w-[1500px] space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-blue-400">BPO Operations</p>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-slate-100 sm:text-3xl">RPI Campaigns</h1>
          <p className="mt-1 text-sm text-slate-400">Automated Right Party Identification across uploaded contact batches.</p>
        </div>
        <Button onClick={() => setOpen(true)} data-testid="create-campaign-btn" className="gap-2"><Plus className="h-4 w-4" />New campaign</Button>
      </div>

      <KpiGrid stats={dash?.stats} />

      <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/70">
        <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <h2 className="font-display text-sm font-semibold text-slate-200">All campaigns</h2>
          <span className="font-mono text-xs text-slate-500">{campaigns?.length ?? 0} total</span>
        </div>
        {!loading && !campaigns?.length && (
          <div className="py-16 text-center text-sm text-slate-500" data-testid="campaigns-empty">No campaigns yet. Create one to upload your first batch.</div>
        )}
        <table className="w-full text-sm" data-testid="campaigns-table">
          <tbody>
            {campaigns?.map((c) => (
              <tr key={c.id} onClick={() => nav(`/rpi/campaigns/${c.id}`)} data-testid={`campaign-row-${c.id}`}
                className="cursor-pointer border-b border-slate-800/60 transition-colors hover:bg-slate-800/40">
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-100">{c.name}</div>
                  <div className="font-mono text-[11px] text-slate-500">agent {c.agent_name || "— not set"} · {c.voice_gender} voice · created {fmtTime(c.created_at)}</div>
                  <BucketCounts s={c.stats} cid={c.id} />
                </td>
                <td className="px-4 py-3"><StatusBadge value={c.status} testId={`campaign-status-${c.id}`} /></td>
                <td className="w-1/4 px-4 py-3"><Bar s={c.stats} /></td>
                <td className="px-4 py-3 text-right font-mono text-xs text-slate-400">
                  <span className="text-emerald-400">{c.stats.RPC_CONFIRMED}</span> / {c.stats.total} · {c.stats.rpi_rate}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <CampaignFormDialog open={open} onOpenChange={setOpen} onSaved={(c) => nav(`/rpi/campaigns/${c.id}`)} />
    </div>
  );
}
