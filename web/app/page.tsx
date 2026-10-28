"use client";
import { useCallback, useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { api } from "@/lib/api";
import AuthForm from "@/components/AuthForm";
import Dashboard from "@/components/Dashboard";
import SetPassword from "@/components/SetPassword";
import Team from "@/components/Team";

function Onboarding({ onDone }: { onDone: () => void }) {
  const [company, setCompany] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const { error } = await supabase.rpc("onboard_company", { p_company_name: company });
    if (error) setErr(error.message); else onDone();
  }
  return (
    <form onSubmit={submit} className="mx-auto max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow">
      <h1 className="text-xl font-bold">Willkommen! Wie heißt dein Betrieb?</h1>
      <input className="min-h-12 w-full rounded-xl border border-slate-300 px-3" placeholder="Firmenname" required
        value={company} onChange={(e) => setCompany(e.target.value)} />
      {err && <p className="text-sm text-red-600">{err}</p>}
      <button className="min-h-12 w-full rounded-xl bg-slate-900 font-bold text-white">Los geht's</button>
    </form>
  );
}

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [needsPassword, setNeedsPassword] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [role, setRole] = useState<string | null>(null);
  const [view, setView] = useState<"projects" | "team">("projects");

  useEffect(() => {
    // Einladungs-/Reset-Link: Typ steckt im URL-Hash, VOR dem Auslesen der Session prüfen
    const h = window.location.hash;
    if (h.includes("type=invite") || h.includes("type=recovery")) setNeedsPassword(true);
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setReady(true); });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session) { setRole(null); return; }
    api<{ role: string }>("/api/v1/me").then((m) => setRole(m.role)).catch(() => setRole(null));
  }, [session, reloadKey]);

  const onNoCompany = useCallback(() => setNeedsOnboarding(true), []);
  const isManager = role === "owner" || role === "admin";

  if (!ready) return null;
  if (session && needsPassword) {
    return <SetPassword onDone={() => { window.history.replaceState(null, "", window.location.pathname); setNeedsPassword(false); }} />;
  }
  return (
    <main className="mx-auto min-h-screen max-w-xl bg-slate-100 p-4">
      {!session ? <AuthForm /> : (
        <>
          <header className="mb-4 flex items-center justify-between">
            <h1 className="text-lg font-bold">Job-Costing</h1>
            <nav className="flex items-center gap-4 text-sm">
              {isManager && (
                <button className="min-h-11 font-medium underline" onClick={() => setView(view === "team" ? "projects" : "team")}>
                  {view === "team" ? "Projekte" : "Team"}
                </button>
              )}
              <button className="min-h-11 underline" onClick={() => supabase.auth.signOut()}>Abmelden</button>
            </nav>
          </header>
          {needsOnboarding
            ? <Onboarding onDone={() => { setNeedsOnboarding(false); setReloadKey((k) => k + 1); }} />
            : view === "team" && isManager ? <Team /> : <Dashboard key={reloadKey} onNoCompany={onNoCompany} />}
        </>
      )}
    </main>
  );
}
