import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bell,
  ChevronDown,
  CircleHelp,
  Database,
  LayoutDashboard,
  Menu,
  Radar,
  Settings,
  Shield,
  ShieldCheck,
  X,
} from "lucide-react";
import { getHealth } from "./api/client";

const navigation = [
  { label: "Overview", icon: LayoutDashboard, active: true },
  { label: "Signals", icon: Activity },
  { label: "Alerts", icon: Bell },
  { label: "Datasets", icon: Database },
];

function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getHealth()
      .then(({ status }) => {
        if (active) setApiStatus(status === "ok" ? "online" : "offline");
      })
      .catch((error: unknown) => {
        if (active) {
          setApiStatus("offline");
          setApiError(error instanceof Error ? error.message : "Unknown API connection error");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100">
      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-64 flex-col border-r border-white/[0.07] bg-navy-950 px-5 py-6 transition-transform lg:translate-x-0 ${
          menuOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between">
          <a className="flex items-center gap-3" href="/" aria-label="SIBERLENS AI home">
            <span className="grid h-10 w-10 place-items-center rounded-xl border border-accent-400/20 bg-accent-400/10 text-accent-400">
              <Radar size={22} strokeWidth={1.8} />
            </span>
            <span>
              <span className="block text-sm font-bold tracking-[0.16em] text-white">SIBERLENS</span>
              <span className="mt-0.5 block text-[10px] font-semibold tracking-[0.23em] text-slate-500">
                INTELLIGENCE
              </span>
            </span>
          </a>
          <button
            className="rounded-lg p-2 text-slate-400 hover:bg-white/5 lg:hidden"
            onClick={() => setMenuOpen(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mt-12">
          <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-600">
            Workspace
          </p>
          <nav aria-label="Primary navigation" className="space-y-1">
            {navigation.map(({ label, icon: Icon, active }) => (
              <a
                key={label}
                href="#"
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                  active
                    ? "bg-accent-400/[0.09] font-medium text-accent-400"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                }`}
              >
                <Icon size={17} strokeWidth={1.8} />
                {label}
                {label === "Alerts" && (
                  <span className="ml-auto rounded-md border border-white/[0.08] px-1.5 py-0.5 text-[10px] text-slate-500">
                    —
                  </span>
                )}
              </a>
            ))}
          </nav>
        </div>

        <div className="mt-auto">
          <div className="mb-5 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
            <div className="mb-3 flex items-center gap-2 text-xs font-medium text-slate-300">
              <ShieldCheck size={15} className="text-accent-400" />
              Defensive monitoring
            </div>
            <p className="text-xs leading-5 text-slate-500">
              Built to support early awareness and responsible response.
            </p>
          </div>
          <a
            href="#"
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
          >
            <Settings size={17} strokeWidth={1.8} />
            Settings
          </a>
          <div className="mt-4 flex items-center gap-3 border-t border-white/[0.07] pt-5">
            <div className="grid h-9 w-9 place-items-center rounded-full bg-slate-800 text-xs font-semibold text-slate-300">
              SL
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-slate-200">Analyst workspace</p>
              <p className="mt-1 text-[10px] text-slate-500">Prototype environment</p>
            </div>
            <ChevronDown size={15} className="text-slate-500" />
          </div>
        </div>
      </aside>

      {menuOpen && (
        <button
          aria-label="Close navigation overlay"
          className="fixed inset-0 z-20 bg-black/60 lg:hidden"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <main className="min-h-screen lg:pl-64">
        <header className="flex h-[72px] items-center justify-between border-b border-white/[0.07] px-5 sm:px-8">
          <div className="flex items-center gap-3">
            <button
              className="rounded-lg p-2 text-slate-400 hover:bg-white/5 lg:hidden"
              onClick={() => setMenuOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={19} />
            </button>
            <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
              Workspace <span className="text-slate-700">/</span>{" "}
              <span className="text-slate-300">Overview</span>
            </div>
            <span className="text-sm font-semibold text-slate-200 sm:hidden">Overview</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  apiStatus === "online"
                    ? "bg-accent-400"
                    : apiStatus === "offline"
                      ? "bg-rose-400"
                      : "bg-amber-400"
                }`}
              />
              API {apiStatus}
            </div>
            <button
              aria-label="Help"
              className="rounded-lg p-2 text-slate-500 transition hover:bg-white/5 hover:text-slate-300"
            >
              <CircleHelp size={18} />
            </button>
            <button
              aria-label="Notifications"
              className="relative rounded-lg p-2 text-slate-500 transition hover:bg-white/5 hover:text-slate-300"
            >
              <Bell size={18} />
              <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-accent-400" />
            </button>
          </div>
        </header>

        <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
            <div>
              <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent-400/15 bg-accent-400/[0.06] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-accent-400">
                <Shield size={12} />
                Defensive intelligence
              </div>
              <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-[30px]">
                Intelligence overview
              </h1>
              <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
                A clear view of your monitored data and emerging signals.
              </p>
            </div>
            <div className="flex items-center gap-2 self-start rounded-lg border border-white/[0.08] bg-white/[0.025] px-3 py-2 text-xs text-slate-400 sm:self-auto">
              <span className="h-1.5 w-1.5 rounded-full bg-slate-600" />
              No data sources connected
            </div>
          </div>

          {apiError && (
            <div
              role="status"
              className="mt-6 rounded-lg border border-rose-400/20 bg-rose-400/[0.06] px-4 py-3 text-xs text-rose-200"
            >
              API connection unavailable: {apiError}
            </div>
          )}

          <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {["Active signals", "Open alerts", "Monitored sources", "Last updated"].map((item) => (
              <section key={item} className="panel-card min-h-[122px] p-5">
                <p className="text-xs font-medium text-slate-500">{item}</p>
                <div className="mt-5 flex items-end justify-between">
                  <span className="text-2xl font-semibold tracking-tight text-slate-300">—</span>
                  <span className="text-[10px] text-slate-600">Awaiting data</span>
                </div>
              </section>
            ))}
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.65fr_1fr]">
            <section className="panel-card min-h-[350px] p-5 sm:p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-200">Signal activity</h2>
                  <p className="mt-1 text-xs text-slate-500">Activity will appear when data is connected</p>
                </div>
                <button className="rounded-lg border border-white/[0.08] px-3 py-1.5 text-xs text-slate-400">
                  Last 7 days <ChevronDown size={13} className="ml-1 inline" />
                </button>
              </div>
              <div className="flex h-[250px] flex-col items-center justify-center">
                <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/[0.07] bg-white/[0.025] text-slate-600">
                  <Activity size={21} strokeWidth={1.5} />
                </div>
                <p className="mt-4 text-sm font-medium text-slate-400">No signal activity yet</p>
                <p className="mt-1 max-w-xs text-center text-xs leading-5 text-slate-600">
                  Connect a data source to begin viewing activity over time.
                </p>
              </div>
            </section>
            <section className="panel-card min-h-[350px] p-5 sm:p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-200">Recent alerts</h2>
                  <p className="mt-1 text-xs text-slate-500">Latest items requiring attention</p>
                </div>
                <AlertTriangle size={17} className="text-slate-600" />
              </div>
              <div className="flex h-[250px] flex-col items-center justify-center">
                <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/[0.07] bg-white/[0.025] text-slate-600">
                  <ShieldCheck size={21} strokeWidth={1.5} />
                </div>
                <p className="mt-4 text-sm font-medium text-slate-400">You’re all caught up</p>
                <p className="mt-1 max-w-xs text-center text-xs leading-5 text-slate-600">
                  Alerts will be listed here when available.
                </p>
              </div>
            </section>
          </div>

          <footer className="mt-8 flex flex-col justify-between gap-2 border-t border-white/[0.06] pt-5 text-[10px] text-slate-600 sm:flex-row">
            <span>SIBERLENS AI · Defensive social cyber intelligence</span>
            <span>Prototype foundation · No analytics configured</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default App;
