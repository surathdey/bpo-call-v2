import { NavLink, Outlet } from "react-router-dom";
import { Activity, FileClock, PhoneOutgoing, Settings2, ShieldCheck } from "lucide-react";
import { api, usePoll } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/rpi/campaigns", label: "RPI Campaigns", icon: PhoneOutgoing, id: "nav-campaigns" },
  { to: "/rpi/settings", label: "Provider & Defaults", icon: Settings2, id: "nav-settings" },
  { to: "/rpi/audit", label: "Audit Log", icon: FileClock, id: "nav-audit" },
];

const ModeIndicator = () => {
  const { data } = usePoll(() => api.get("/dashboard").then((r) => r.data), 3000);
  if (!data) return null;
  const live = data.call_mode === "live";
  return (
    <div className="flex items-center gap-4 text-xs" data-testid="system-status">
      <span className={cn("flex items-center gap-2 rounded-md border px-2.5 py-1 font-mono uppercase tracking-wide",
        live ? "border-emerald-500/30 text-emerald-400" : "border-amber-500/30 text-amber-400")} data-testid="call-mode-indicator">
        <span className={cn("h-1.5 w-1.5 rounded-full", live ? "bg-emerald-500" : "bg-amber-500")} />
        {live ? "Live · Vapi + ElevenLabs" : "Simulation mode"}
      </span>
      <span className="hidden items-center gap-1.5 font-mono text-slate-400 md:flex" data-testid="running-campaigns-count">
        <Activity className="h-3.5 w-3.5" /> {data.running} running · {data.stats.calling} on call
      </span>
    </div>
  );
};

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-[#0B0F17] text-slate-200">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-800/80 bg-[#0d121c] lg:flex">
        <div className="flex h-14 items-center gap-2.5 border-b border-slate-800/80 px-5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-500"><ShieldCheck className="h-4 w-4 text-white" /></div>
          <div className="leading-tight">
            <div className="font-display text-sm font-bold text-slate-100">RevLoop</div>
            <div className="font-mono text-[10px] uppercase tracking-widest text-slate-500">BPO · RPI Module</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 p-3">
          <div className="px-2 pb-2 pt-3 font-mono text-[10px] uppercase tracking-widest text-slate-600">Identity Verification</div>
          {NAV.map(({ to, label, icon: Icon, id }) => (
            <NavLink key={to} to={to} data-testid={id}
              className={({ isActive }) => cn("flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                isActive ? "bg-blue-500/10 text-blue-300" : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200")}>
              <Icon className="h-4 w-4" /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-800/80 p-4 font-mono text-[10px] leading-relaxed text-slate-600">
          Callback commitment only — no live transfer.
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-800/80 bg-[#0B0F17]/85 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <div className="flex items-center gap-3 lg:hidden">
            {NAV.map(({ to, icon: Icon, id }) => (
              <NavLink key={to} to={to} data-testid={`m-${id}`} className="text-slate-400 hover:text-slate-100"><Icon className="h-4 w-4" /></NavLink>
            ))}
          </div>
          <div className="hidden font-mono text-xs uppercase tracking-widest text-slate-500 lg:block">Right Party Identification · Outbound</div>
          <ModeIndicator />
        </header>
        <main className="grid-noise flex-1 p-4 sm:p-6 lg:p-8"><Outlet /></main>
      </div>
    </div>
  );
}
