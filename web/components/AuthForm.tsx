"use client";
import { useState } from "react";
import { supabase } from "@/lib/supabase";

export default function AuthForm() {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    const { error, data } =
      mode === "login"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });
    if (error) setMsg(error.message);
    else if (mode === "signup" && !data.session) setMsg("Bitte bestätige deine E-Mail und melde dich dann an.");
    setBusy(false);
  }

  return (
    <form onSubmit={submit} className="mx-auto mt-16 w-full max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow">
      <h1 className="text-xl font-bold">{mode === "login" ? "Anmelden" : "Konto erstellen"}</h1>
      <input className="w-full rounded-lg border p-3" type="email" placeholder="E-Mail" required
        value={email} onChange={(e) => setEmail(e.target.value)} />
      <input className="w-full rounded-lg border p-3" type="password" placeholder="Passwort (min. 8 Zeichen)"
        required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
      {msg && <p className="text-sm text-red-600">{msg}</p>}
      <button disabled={busy} className="w-full rounded-lg bg-slate-900 p-3 font-semibold text-white disabled:opacity-50">
        {mode === "login" ? "Anmelden" : "Registrieren"}
      </button>
      <button type="button" className="w-full text-sm text-slate-600 underline"
        onClick={() => setMode(mode === "login" ? "signup" : "login")}>
        {mode === "login" ? "Noch kein Konto? Registrieren" : "Schon registriert? Anmelden"}
      </button>
    </form>
  );
}
