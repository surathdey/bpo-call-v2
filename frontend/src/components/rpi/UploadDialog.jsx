import { useRef, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, FileUp, XCircle } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api, errMsg } from "@/lib/api";
import { cn } from "@/lib/utils";

const REQUIRED = ["name", "phone"];

const quickHeaderCheck = async (file) => {
  const head = (await file.slice(0, 2048).text()).split(/\r?\n/)[0].toLowerCase();
  const cols = head.split(",").map((c) => c.trim().replace(/"/g, ""));
  const has = (k) => cols.some((c) => c.includes(k));
  return REQUIRED.filter((k) => !has(k));
};

const Metric = ({ label, value, tone, testId }) => (
  <div className="rounded-md border border-slate-800 bg-slate-900/70 p-3" data-testid={testId}>
    <div className="font-mono text-[10px] uppercase tracking-widest text-slate-500">{label}</div>
    <div className={cn("mt-1 font-mono text-xl font-bold", tone)}>{value}</div>
  </div>
);

export const UploadDialog = ({ open, onOpenChange, campaignId, onImported }) => {
  const [file, setFile] = useState(null);
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  const reset = () => { setFile(null); setReport(null); };
  const close = (v) => { if (!v) reset(); onOpenChange(v); };

  const pick = async (f) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".csv")) return toast.error("Please choose a .csv file");
    const missing = await quickHeaderCheck(f);
    if (missing.length) toast.warning(`Header may be missing: ${missing.join(", ")}`);
    setFile(f);
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const { data } = await api.post(`/campaigns/${campaignId}/contacts/validate`, fd);
      setReport(data);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/campaigns/${campaignId}/contacts/import`, fd);
      toast.success(`Imported ${data.imported} contacts · ${data.rejected} rejected`);
      onImported?.();
      close(false);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="max-w-3xl border-slate-800 bg-[#0f1520]" data-testid="csv-upload-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">Upload contact batch</DialogTitle>
          <DialogDescription>
            Columns: <code className="text-blue-300">name, phone</code> (required) · <code className="text-slate-400">customer_id, language</code> (optional). Phones normalised to E.164.
          </DialogDescription>
        </DialogHeader>
        {!report ? (
          <div data-testid="csv-upload-dropzone" onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
            className={cn("flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-14 text-center transition-colors",
              drag ? "border-blue-500 bg-blue-500/5" : "border-slate-700 hover:border-slate-500")}>
            <FileUp className="h-8 w-8 text-slate-500" />
            <p className="mt-3 text-sm text-slate-300">{busy ? "Validating…" : "Drop a CSV here or click to browse"}</p>
            <p className="mt-1 font-mono text-[11px] text-slate-600">max 10,000 rows · 5 MB</p>
            <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" data-testid="csv-file-input"
              onChange={(e) => pick(e.target.files[0])} />
          </div>
        ) : (
          <div className="space-y-4" data-testid="csv-validation-summary">
            <div className="flex items-center gap-2 font-mono text-xs text-slate-400">{file?.name}</div>
            {report.header_errors.length > 0 && (
              <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300" data-testid="csv-header-errors">
                {report.header_errors.map((h) => <div key={h} className="flex gap-2"><XCircle className="mt-0.5 h-4 w-4 shrink-0" />{h}</div>)}
              </div>
            )}
            <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
              <Metric label="Rows" value={report.total_rows} testId="csv-total-rows" />
              <Metric label="Valid" value={report.valid_count} tone="text-emerald-400" testId="csv-valid-count" />
              <Metric label="Rejected" value={report.invalid_count} tone="text-rose-400" testId="csv-invalid-count" />
              <Metric label="Dup in file" value={report.duplicates_in_file} tone="text-amber-400" testId="csv-dup-file" />
              <Metric label="Dup existing" value={report.duplicates_existing} tone="text-amber-400" testId="csv-dup-existing" />
              <Metric label="DNC blocked" value={report.dnc_blocked} tone="text-slate-300" testId="csv-dnc-blocked" />
            </div>
            <div className="flex flex-wrap gap-2 font-mono text-[11px] text-slate-400">
              {Object.entries(report.language_breakdown).map(([k, v]) => (
                <span key={k} className="rounded border border-slate-700 px-2 py-0.5">{k}: {v}</span>))}
              {report.warnings > 0 && <span className="flex items-center gap-1 text-amber-400"><AlertTriangle className="h-3 w-3" />{report.warnings} rows with warnings</span>}
            </div>
            {report.invalid.length > 0 ? (
              <ScrollArea className="h-56 rounded-md border border-slate-800">
                <table className="w-full text-xs" data-testid="csv-invalid-table">
                  <thead className="sticky top-0 bg-slate-900 font-mono text-[10px] uppercase tracking-wider text-slate-500">
                    <tr><th className="p-2 text-left">Row</th><th className="p-2 text-left">Name</th><th className="p-2 text-left">Phone</th><th className="p-2 text-left">Reason</th></tr>
                  </thead>
                  <tbody>
                    {report.invalid.map((r) => (
                      <tr key={r.row} className="border-t border-slate-800/70">
                        <td className="p-2 font-mono text-slate-500">{r.row}</td>
                        <td className="p-2">{r.name || <em className="text-slate-600">blank</em>}</td>
                        <td className="p-2 font-mono">{r.raw_phone || "—"}</td>
                        <td className="p-2 text-rose-300">{r.reasons.join("; ")}</td>
                      </tr>))}
                  </tbody>
                </table>
              </ScrollArea>
            ) : (
              <div className="flex items-center gap-2 text-sm text-emerald-400"><CheckCircle2 className="h-4 w-4" /> All rows passed validation</div>
            )}
          </div>
        )}
        <DialogFooter>
          {report && <Button variant="ghost" onClick={reset} data-testid="csv-choose-another-btn">Choose another file</Button>}
          <Button variant="ghost" onClick={() => close(false)} data-testid="csv-cancel-btn">Cancel</Button>
          <Button onClick={confirm} disabled={!report || busy || report.valid_count === 0} data-testid="csv-confirm-import-btn">
            {busy && report ? "Importing…" : `Import ${report?.valid_count ?? 0} valid rows`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
