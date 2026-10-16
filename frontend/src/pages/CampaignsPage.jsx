import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, fmtTime, usePoll } from "@/lib/api";
import { KpiGrid } from "@/components/rpi/KpiGrid";
import { StatusBadge } from "@/components/rpi/Badges";
import { CampaignFormDialog } from "@/components/rpi/CampaignFormDialog";

const Bar = ({ s }) => {
  const total = s.total || 1;
  const seg = [["RPI_CONFIRMED", "bg-emerald-500"], ["WRONG_PARTY", "bg-rose-500"], ["NO_ANSWER_VOICEMAIL", "bg-amber-500"], ["FAILED_NUMBER", "bg-slate-500"]];
  return (
    <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
      {seg.map(([k, c]) => <div key={k} className={c} style={{ width: `${(s[k] / total) * 100}%` }} />)}
    </div>
  );
};

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
                  <div className="font-mono text-[11px] text-slate-500">{c.language} · {c.voice_gender} voice · created {fmtTime(c.created_at)}</div>
                </td>
                <td className="px-4 py-3"><StatusBadge value={c.status} testId={`campaign-status-${c.id}`} /></td>
                <td className="w-1/4 px-4 py-3"><Bar s={c.stats} /></td>
                <td className="px-4 py-3 text-right font-mono text-xs text-slate-400">
                  <span className="text-emerald-400">{c.stats.RPI_CONFIRMED}</span> / {c.stats.total} · {c.stats.rpi_rate}%
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
