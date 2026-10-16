import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, errMsg, LANGUAGES } from "@/lib/api";

export const CampaignFormDialog = ({ open, onOpenChange, campaign, onSaved }) => {
  const editing = Boolean(campaign);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (campaign) {
      setForm({ name: campaign.name, description: campaign.description, language: campaign.language,
        voice_gender: campaign.voice_gender, voice_id: campaign.voice_id, prompt: campaign.prompt });
    } else {
      api.get("/settings").then(({ data }) => setForm({ name: "", description: "", language: data.default_language,
        voice_gender: data.default_voice_gender, voice_id: "", prompt: data.default_prompt }));
    }
  }, [open, campaign]);

  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v?.target ? v.target.value : v }));

  const save = async () => {
    if (!form.name?.trim()) return toast.error("Campaign name is required");
    setSaving(true);
    try {
      const { data } = editing ? await api.patch(`/campaigns/${campaign.id}`, form) : await api.post("/campaigns", form);
      toast.success(editing ? "Campaign settings saved" : "Campaign created");
      onSaved?.(data);
      onOpenChange(false);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl border-slate-800 bg-[#0f1520]" data-testid="campaign-form-dialog">
        <DialogHeader>
          <DialogTitle className="font-display">{editing ? "Campaign voice & script" : "New RPI campaign"}</DialogTitle>
          <DialogDescription>Voice, language and operator prompt apply to every call in this campaign.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Name</Label>
            <Input data-testid="campaign-name-input" value={form.name || ""} onChange={set("name")} placeholder="Q3 Collections — RPI batch A" />
          </div>
          <div className="space-y-1.5">
            <Label>Description</Label>
            <Input data-testid="campaign-description-input" value={form.description || ""} onChange={set("description")} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Default language</Label>
              <Select value={form.language} onValueChange={set("language")}>
                <SelectTrigger data-testid="campaign-language-select"><SelectValue placeholder="Language" /></SelectTrigger>
                <SelectContent>
                  {LANGUAGES.map((l) => <SelectItem key={l.code} value={l.code} data-testid={`lang-option-${l.code}`}>{l.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Voice</Label>
              <RadioGroup value={form.voice_gender} onValueChange={set("voice_gender")} className="flex h-10 items-center gap-5">
                {["female", "male"].map((g) => (
                  <label key={g} className="flex cursor-pointer items-center gap-2 text-sm capitalize">
                    <RadioGroupItem value={g} data-testid={`campaign-voice-${g}`} /> {g}
                  </label>
                ))}
              </RadioGroup>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Voice profile ID override <span className="text-slate-500">(optional, ElevenLabs voiceId)</span></Label>
            <Input data-testid="campaign-voice-id-input" className="font-mono text-xs" value={form.voice_id || ""}
              onChange={set("voice_id")} placeholder="Leave blank to use the language × gender profile from Settings" />
          </div>
          <div className="space-y-1.5">
            <Label>AI agent prompt (style notes)</Label>
            <Textarea data-testid="campaign-prompt-textarea" rows={5} value={form.prompt || ""} onChange={set("prompt")} />
            <p className="text-xs text-slate-500">Guardrailed: the verification script and hard rules always take precedence. Lines that try to override rules are stripped.</p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} data-testid="campaign-form-cancel">Cancel</Button>
          <Button onClick={save} disabled={saving} data-testid="campaign-form-submit">{saving ? "Saving…" : editing ? "Save" : "Create campaign"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
