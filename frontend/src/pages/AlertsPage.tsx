import AlertTable from "../components/AlertTable";
import type { AlertRecord } from "../types";

const alerts: AlertRecord[] = [];

export default function AlertsPage() {
  return (
    <div className="mx-auto max-w-[1440px] px-5 py-8 sm:px-8 sm:py-10">
      <h1 className="text-2xl font-semibold tracking-tight text-white">Alerts</h1>
      <p className="mt-2 text-sm text-slate-500">Review and triage validated alerts.</p>
      <div className="mt-8">
        <AlertTable alerts={alerts} />
      </div>
    </div>
  );
}
