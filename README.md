# Job-Costing für Handwerksbetriebe

```
jobcosting/
├── supabase/schema.sql      Datenbank (Tabellen, Constraints, RLS, onboard_company)
├── backend/                 FastAPI (app/, tests/, Dockerfile, .env.example)
├── web/                     Next.js-App (komplett, direkt deploybar)
├── render.yaml              Backend-Blueprint für Render (kostenloser Test)
├── setup.sh                 lokale Einrichtung (optional)
└── DEPLOYMENT.md            Produktivbetrieb (Supabase, Fly.io/Render, Vercel)
```

## Online testen (ohne lokale Installation)
Supabase (Free) + Render (Free, Backend) + Vercel (Hobby, Frontend). Schritte siehe Chat bzw. DEPLOYMENT.md.

## Lokal starten
1. Supabase-Projekt anlegen, `supabase/schema.sql` im SQL-Editor ausführen. Lokal unter Authentication → Providers → Email „Confirm email“ ausschalten.
2. `bash setup.sh` (venv, Pakete, `web/.env.local`).
3. `backend/.env` und `web/.env.local` ausfüllen.
4. Terminal A: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload`
   Terminal B: `cd web && npm run dev` → http://localhost:3000

## Erster Test
Registrieren → Firmenname → Projekt anlegen → Stunden buchen → Beleg scannen → Ampel prüfen → Buchung ändern/löschen. Mit zweitem Konto prüfen, dass es keine fremden Projekte sieht.
