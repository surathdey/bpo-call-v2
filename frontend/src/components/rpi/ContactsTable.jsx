import { ChevronRight, Flag } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { DispositionBadge, StatusBadge } from "@/components/rpi/Badges";
import { fmtTime } from "@/lib/api";

const TH = ({ children, className = "" }) => (
  <th className={`whitespace-nowrap px-3 py-2.5 text-left font-mono text-[10px] font-medium uppercase tracking-wider text-slate-500 ${className}`}>{children}</th>
);

export const ContactsTable = ({ rows, selected, onToggle, onToggleAll, onOpen }) => {
  const all = rows.length > 0 && rows.every((r) => selected.has(r.id));
  if (!rows.length) {
    return <div className="py-16 text-center text-sm text-slate-500" data-testid="contacts-empty">No contacts match. Upload a CSV batch to get started.</div>;
  }
  return (
    <div className="thin-scroll overflow-x-auto">
      <table className="w-full text-sm" data-testid="contacts-table">
        <thead className="border-b border-slate-800 bg-slate-900/60">
          <tr>
            <TH className="w-8"><Checkbox checked={all} onCheckedChange={onToggleAll} data-testid="select-all-contacts" /></TH>
            <TH>Phone number</TH><TH>Name</TH><TH>Bank</TH><TH>State</TH><TH>Lang</TH><TH>Call state</TH><TH>Disposition</TH>
            <TH>Category</TH><TH>Tries</TH><TH>Duration</TH><TH>Last called</TH><TH />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-testid={`contact-row-${r.id}`} onClick={() => onOpen(r.id)}
              className="cursor-pointer border-b border-slate-800/60 transition-colors hover:bg-slate-800/40">
              <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                <Checkbox checked={selected.has(r.id)} onCheckedChange={() => onToggle(r.id)} data-testid={`select-contact-${r.id}`} />
              </td>
              <td className="px-3 py-2 font-mono text-xs text-slate-300">{r.phone}</td>
              <td className="px-3 py-2 font-medium text-slate-200">{r.name}</td>
              <td className="px-3 py-2 text-xs text-slate-400">{r.bank_name}</td>
              <td className="px-3 py-2 text-xs text-slate-400">{r.state || "—"}</td>
              <td className="px-3 py-2 font-mono text-xs text-slate-400">{r.language}</td>
              <td className="px-3 py-2">
                <StatusBadge value={r.status} testId={`contact-status-${r.id}`} />
                {r.last_call_status && r.last_call_status !== "completed" && r.status === "completed" &&
                  <div className="mt-0.5 font-mono text-[10px] uppercase text-slate-500">{r.last_call_status}</div>}
              </td>
              <td className="px-3 py-2">
                <div className="flex items-center gap-1.5">
                  <DispositionBadge value={r.disposition} testId={`contact-disposition-${r.id}`} />
                  {r.review_required && <Flag className="h-3.5 w-3.5 text-amber-400" title="Needs review" data-testid={`contact-review-${r.id}`} />}
                </div>
              </td>
              <td className="px-3 py-2 text-xs text-slate-400">{r.last_category || "—"}</td>
              <td className="px-3 py-2 font-mono text-xs text-slate-400">{r.attempts}</td>
              <td className="px-3 py-2 font-mono text-xs text-slate-400">{r.last_duration != null ? `${r.last_duration}s` : "—"}</td>
              <td className="whitespace-nowrap px-3 py-2 text-xs text-slate-500">{fmtTime(r.last_called_at)}</td>
              <td className="px-3 py-2 text-slate-600"><ChevronRight className="h-4 w-4" data-testid={`table-row-action-view-detail-${r.id}`} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
