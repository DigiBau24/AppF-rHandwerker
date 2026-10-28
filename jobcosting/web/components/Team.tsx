"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Member { id: string; email: string | null; full_name: string | null; role: "owner" | "admin" | "member" }
const ROLE: Record<Member["role"], string> = { owner: "Inhaber", admin: "Admin", member: "Mitarbeiter" };

export default function Team() {
  const [members, setMembers] = useState<Member[]>([]);
  const [f, setF] = useState({ email: "", full_name: "", role: "member" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { setMembers(await api<Member[]>("/api/v1/team")); }
    catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      await api("/api/v1/team/invitations", {
        method: "POST",
        body: JSON.stringify({ email: f.email, role: f.role, full_name: f.full_name || null }),
      });
      setMsg({ ok: true, text: `Einladung an ${f.email} gesendet.` });
      setF({ email: "", full_name: "", role: "member" });
      load();
    } catch (e) { setMsg({ ok: false, text: (e as Error).message }); }
    finally { setBusy(false); }
  }

  const input = "min-h-12 w-full rounded-xl border border-slate-300 bg-white px-3 text-base";
  return (
    <div className="space-y-6">
      <form onSubmit={invite} className="space-y-2 rounded-2xl bg-white p-4 shadow">
        <h2 className="font-semibold">Mitarbeiter einladen</h2>
        <input className={input} type="email" required placeholder="E-Mail" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <input className={input} placeholder="Name (optional)" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
        <select className={input} aria-label="Rolle" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
          <option value="member">Mitarbeiter (bucht Stunden und Belege)</option>
          <option value="admin">Admin (legt Projekte an, verwaltet alles)</option>
        </select>
        {msg && <p className={`text-sm ${msg.ok ? "text-green-800" : "text-red-600"}`}>{msg.text}</p>}
        <button disabled={busy} className="min-h-12 w-full rounded-xl bg-slate-900 font-bold text-white disabled:opacity-50">Einladung senden</button>
      </form>
      <ul className="divide-y divide-slate-100 rounded-2xl bg-white px-4 shadow">
        {members.map((m) => (
          <li key={m.id} className="flex items-center justify-between py-3 text-sm">
            <span><b className="font-semibold">{m.full_name || m.email}</b>{m.full_name && <><br /><span className="text-slate-500">{m.email}</span></>}</span>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{ROLE[m.role]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
