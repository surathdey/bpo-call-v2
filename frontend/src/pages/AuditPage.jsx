import { useEffect, useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, fmtTime, usePoll } from "@/lib/api";

const EVENTS = ["campaign_created", "campaign_updated", "contacts_imported", "campaign_launched", "campaign_paused",
  "campaign_completed", "campaign_auto_paused", "contacts_retried", "campaign_exported", "call_finalized",
  "duplicate_callback_ignored", "settings_updated", "webhook_token_rotated", "vapi_connection_test"];

export default function AuditPage() {
  const [event, setEvent] = useState("");
  const { data, reload } = usePoll(() => api.get("/audit", { params: { event: event || undefined } }).then((r) => r.data), 5000);
  useEffect(() => { reload(); }, [event, reload]);
  return (
    <div className="mx-auto max-w-[1500px] space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-blue-400">Compliance</p>
          <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-slate-100 sm:text-3xl">Audit log</h1>
        </div>
        <Select value={event || "ALL"} onValueChange={(v) => setEvent(v === "ALL" ? "" : v)}>
          <SelectTrigger className="w-64" data-testid="audit-log-filter-event"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All events</SelectItem>
            {EVENTS.map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900/70">
        <table className="w-full text-sm" data-testid="audit-log-table">
          <thead className="border-b border-slate-800 font-mono text-[10px] uppercase tracking-wider text-slate-500">
            <tr><th className="p-3 text-left">Time</th><th className="p-3 text-left">Event</th><th className="p-3 text-left">Entity</th><th className="p-3 text-left">Details</th></tr>
          </thead>
          <tbody>
            {data?.map((l) => (
              <tr key={l.id} className="border-b border-slate-800/60" data-testid={`audit-row-${l.id}`}>
                <td className="whitespace-nowrap p-3 text-xs text-slate-500">{fmtTime(l.created_at)}</td>
                <td className="p-3 font-mono text-xs text-blue-300">{l.event}</td>
                <td className="p-3 font-mono text-[11px] text-slate-500">{l.entity_type} {l.entity_id?.slice(-6)}</td>
                <td className="break-all p-3 font-mono text-[11px] text-slate-400">
                  {Object.entries(l.details || {}).map(([k, v]) => <span key={k} className="mr-3">{k}=<span className="text-slate-300">{Array.isArray(v) ? v.join(",") : String(v)}</span></span>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && !data.length && <div className="py-12 text-center text-sm text-slate-500">No audit events.</div>}
      </div>
    </div>
  );
}
