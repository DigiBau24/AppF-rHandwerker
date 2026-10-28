"use client";
import { useState } from "react";
import { supabase } from "@/lib/supabase";

// Wird nach Klick auf den Einladungs-/Reset-Link gezeigt: Passwort festlegen.
export default function SetPassword({ onDone }: { onDone: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const { error } = await supabase.auth.updateUser({ password: pw });
    if (error) setErr(error.message); else onDone();
  }
  return (
    <form onSubmit={submit} className="mx-auto mt-16 max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow">
      <h1 className="text-xl font-bold">Passwort festlegen</h1>
      <input className="min-h-12 w-full rounded-xl border border-slate-300 px-3" type="password" required minLength={8}
        placeholder="Neues Passwort (min. 8 Zeichen)" value={pw} onChange={(e) => setPw(e.target.value)} />
      {err && <p className="text-sm text-red-600">{err}</p>}
      <button className="min-h-12 w-full rounded-xl bg-slate-900 font-bold text-white">Speichern</button>
    </form>
  );
}
