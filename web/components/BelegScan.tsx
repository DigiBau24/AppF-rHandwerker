"use client";
import { useState } from "react";
import { api, ProjectStatus } from "@/lib/api";

interface Scan {
  extracted: { grosshaendler: string | null; rechnungs_datum: string | null; betrag_netto: string | null };
  raw: Record<string, unknown>;
}

export default function BelegScan({ projects, onDone, onCancel }: {
  projects: ProjectStatus[]; onDone: () => void; onCancel: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const [scanned, setScanned] = useState(false);
  const [f, setF] = useState({
    grosshaendler: "", rechnungs_datum: "", betrag_netto: "", projekt_id: projects[0]?.projekt_id ?? "",
  });

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await api<Scan>("/api/v1/material-costs/scan", { method: "POST", body: fd });
      setRaw(res.raw);
      setF((p) => ({
        ...p,
        grosshaendler: res.extracted.grosshaendler ?? "",
        rechnungs_datum: res.extracted.rechnungs_datum ?? "",
        betrag_netto: res.extracted.betrag_netto ?? "",
      }));
      setScanned(true);
    } catch (e) {
      setErr((e as Error).message);
      setScanned(true); // manuell weiter erfassen ist erlaubt
    } finally {
      setBusy(false);
    }
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await api("/api/v1/material-costs", { method: "POST", body: JSON.stringify({ ...f, gemini_raw_json: raw }) });
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  const input = "w-full min-h-12 rounded-xl border border-slate-300 bg-white px-3 text-base";
  const label = "mb-1 mt-4 block text-xs font-semibold text-slate-600";
  return (
    <section className="rounded-2xl bg-white p-4 shadow">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Beleg erfassen</h2>
        <button className="text-sm underline" onClick={onCancel}>Abbrechen</button>
      </div>
      {!scanned && (
        <label className="mt-4 flex min-h-32 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 p-4 text-center text-slate-600">
          {busy ? "KI liest den Beleg …" : "Foto aufnehmen oder Datei wählen (JPG, PNG, PDF)"}
          <input type="file" accept="image/*,application/pdf" capture="environment" className="sr-only"
            onChange={onFile} disabled={busy} />
        </label>
      )}
      {scanned && (
        <form onSubmit={save}>
          {raw && <p className="mt-3 rounded-lg bg-green-100 p-2 text-sm text-green-900">KI-Auslesen fertig – bitte Werte prüfen.</p>}
          {err && <p className="mt-3 text-sm text-red-600">{err}</p>}
          <label className={label} htmlFor="gh">Großhändler</label>
          <input id="gh" className={input} required value={f.grosshaendler} onChange={(e) => setF({ ...f, grosshaendler: e.target.value })} />
          <label className={label} htmlFor="dt">Rechnungsdatum</label>
          <input id="dt" className={input} type="date" required value={f.rechnungs_datum} onChange={(e) => setF({ ...f, rechnungs_datum: e.target.value })} />
          <label className={label} htmlFor="nt">Betrag netto (€)</label>
          <input id="nt" className={input} type="number" step="0.01" required value={f.betrag_netto} onChange={(e) => setF({ ...f, betrag_netto: e.target.value })} />
          <label className={label} htmlFor="pj">Projekt</label>
          <select id="pj" className={input} value={f.projekt_id} onChange={(e) => setF({ ...f, projekt_id: e.target.value })}>
            {projects.map((p) => <option key={p.projekt_id} value={p.projekt_id}>{p.projekt_name}</option>)}
          </select>
          <button className="mt-6 min-h-12 w-full rounded-xl bg-slate-900 font-bold text-white">Material buchen</button>
        </form>
      )}
    </section>
  );
}
