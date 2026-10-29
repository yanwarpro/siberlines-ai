import { useEffect, useState } from "react";
import {
  Activity,
  Bell,
  ChevronDown,
  CircleHelp,
  Database,
  LayoutDashboard,
  Menu,
  Radar,
  Settings,
  X,
} from "lucide-react";
import { getHealth } from "./api/client";
import AlertsPage from "./pages/AlertsPage";
import AnalysisPage from "./pages/AnalysisPage";
import Dashboard from "./pages/Dashboard";
import DatasetPage from "./pages/DatasetPage";
import type { PageName } from "./types";

const navigation: { label: string; page: PageName; icon: typeof LayoutDashboard }[] = [
  { label: "Overview", page: "overview", icon: LayoutDashboard },
  { label: "Analysis", page: "analysis", icon: Activity },
  { label: "Alerts", page: "alerts", icon: Bell },
  { label: "Datasets", page: "datasets", icon: Database },
];

const pageTitles: Record<PageName, string> = {
  overview: "Overview",
  datasets: "Datasets",
  analysis: "Analysis",
  alerts: "Alerts",
};

function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [page, setPage] = useState<PageName>("overview");
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

  function renderPage() {
    switch (page) {
      case "datasets":
        return <DatasetPage />;
      case "analysis":
        return <AnalysisPage />;
      case "alerts":
        return <AlertsPage />;
      case "overview":
        return <Dashboard apiError={apiError} />;
    }
  }

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
            {navigation.map(({ label, page: targetPage, icon: Icon }) => (
              <button
                key={targetPage}
                type="button"
                aria-current={page === targetPage ? "page" : undefined}
                onClick={() => {
                  setPage(targetPage);
                  setMenuOpen(false);
                }}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition ${
                  page === targetPage
                    ? "bg-accent-400/[0.09] font-medium text-accent-400"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                }`}
              >
                <Icon size={17} strokeWidth={1.8} />
                {label}
              </button>
            ))}
          </nav>
        </div>

        <div className="mt-auto">
          <div className="mb-5 rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
            <div className="mb-3 flex items-center gap-2 text-xs font-medium text-slate-300">
              <span className="text-accent-400"><Radar size={15} /></span>
              Defensive monitoring
            </div>
            <p className="text-xs leading-5 text-slate-500">
              Built to support early awareness and responsible response.
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-500">
            <Settings size={17} strokeWidth={1.8} />
            Settings (not configured)
          </div>
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
              <span className="text-slate-300">{pageTitles[page]}</span>
            </div>
            <span className="text-sm font-semibold text-slate-200 sm:hidden">{pageTitles[page]}</span>
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
            </button>
          </div>
        </header>

        {renderPage()}

        <footer className="mx-auto flex max-w-[1440px] flex-col justify-between gap-2 border-t border-white/[0.06] px-5 py-5 text-[10px] text-slate-600 sm:flex-row sm:px-8">
          <span>SIBERLENS AI · Defensive social cyber intelligence</span>
          <span>Prototype foundation · No analytics configured</span>
        </footer>
      </main>
    </div>
  );
}

export default App;
