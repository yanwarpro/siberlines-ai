import { useState } from "react";
import { LockKeyhole, Radar } from "lucide-react";
import { supabase } from "../api/supabase";

export default function AuthScreen({ authError }: { authError?: string | null }) {
  const [mode, setMode] = useState<"sign_in" | "sign_up">("sign_in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      if (mode === "sign_in") {
        const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
        if (authError) throw authError;
      } else {
        const { data, error: authError } = await supabase.auth.signUp({ email, password });
        if (authError) throw authError;
        if (!data.session) {
          setMessage("Akun dibuat. Periksa email untuk konfirmasi sebelum masuk.");
        }
      }
    } catch (authError: unknown) {
      setError(authError instanceof Error ? authError.message : "Autentikasi gagal.");
    } finally {
      setBusy(false);
    }
  }

  if (!supabase) {
    return (
      <main className="grid min-h-screen place-items-center bg-navy-950 px-5 py-10 text-slate-100">
        <section className="panel-card w-full max-w-lg p-6 sm:p-8">
          <h1 className="text-lg font-semibold text-white">Autentikasi belum dikonfigurasi</h1>
          <p className="mt-3 text-xs leading-6 text-slate-400">
            Tambahkan <code>VITE_SUPABASE_URL</code> dan <code>VITE_SUPABASE_ANON_KEY</code> pada
            environment frontend, serta <code>SUPABASE_URL</code> dan <code>SUPABASE_ANON_KEY</code>
            pada backend. Gunakan hanya publishable/anon key, bukan service-role key.
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-navy-950 px-5 py-10 text-slate-100">
      <section className="panel-card w-full max-w-md p-6 sm:p-8">
        <div className="flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl border border-accent-400/20 bg-accent-400/10 text-accent-400">
            <Radar size={22} />
          </span>
          <div>
            <p className="text-sm font-bold tracking-[0.16em] text-white">SIBERLENS</p>
            <p className="mt-1 text-[10px] uppercase tracking-[0.2em] text-slate-500">
              Secure analyst access
            </p>
          </div>
        </div>
        <h1 className="mt-8 text-xl font-semibold text-white">
          {mode === "sign_in" ? "Sign in to your workspace" : "Create an analyst account"}
        </h1>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          Authentication is verified by Supabase Auth before the API allows access to data or RSS management.
        </p>
        {authError && (
          <p className="mt-4 rounded-lg border border-rose-400/20 bg-rose-400/[0.06] p-3 text-xs text-rose-200" role="alert">
            {authError}
          </p>
        )}
        <form className="mt-6 space-y-4" onSubmit={(event) => void submit(event)}>
          <label className="block text-xs text-slate-400">
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-2 w-full rounded-lg border border-white/[0.1] bg-navy-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent-400/50"
            />
          </label>
          <label className="block text-xs text-slate-400">
            Password
            <input
              type="password"
              autoComplete={mode === "sign_in" ? "current-password" : "new-password"}
              minLength={8}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-lg border border-white/[0.1] bg-navy-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent-400/50"
            />
          </label>
          {error && <p className="rounded-lg border border-rose-400/20 bg-rose-400/[0.06] p-3 text-xs text-rose-200" role="alert">{error}</p>}
          {message && <p className="rounded-lg border border-emerald-400/20 bg-emerald-400/[0.06] p-3 text-xs text-emerald-200" role="status">{message}</p>}
          <button
            type="submit"
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-accent-400 px-4 py-2.5 text-sm font-semibold text-navy-950 transition hover:bg-accent-300 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <LockKeyhole size={15} />
            {busy ? "Please wait…" : mode === "sign_in" ? "Sign in" : "Create account"}
          </button>
        </form>
        <button
          type="button"
          onClick={() => {
            setMode(mode === "sign_in" ? "sign_up" : "sign_in");
            setError(null);
            setMessage(null);
          }}
          className="mt-5 w-full text-center text-xs text-slate-500 transition hover:text-slate-300"
        >
          {mode === "sign_in" ? "Need an account? Create one" : "Already have an account? Sign in"}
        </button>
      </section>
    </main>
  );
}
