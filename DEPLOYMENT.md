# Deployment

Architektur: **Vercel** (Next.js) → **Fly.io/Railway** (FastAPI, Docker) → **Supabase** (Postgres + Auth).

## 1. Supabase
1. Projekt anlegen (Region: Frankfurt/EU), dann `supabase/schema.sql` im SQL-Editor ausführen.
2. **Authentication → URL Configuration:** *Site URL* = deine Frontend-URL (z. B. `https://app.deinedomain.de`), unter *Redirect URLs* dieselbe URL eintragen. Sonst funktionieren Einladungs-Links nicht.
3. **Authentication → SMTP:** eigenen SMTP-Anbieter eintragen. Der Standard-Versand ist stark limitiert und nicht für Produktion gedacht. Einladungs-Mail-Text unter *Email Templates* auf Deutsch anpassen.
4. **Database → Backups** aktivieren (Pro-Plan: tägliche Backups, Point-in-Time optional). Für Buchhaltungsdaten empfohlen.
5. Notiere: Project URL, `anon`-Key, `service_role`/Secret-Key, DB-Connection-String (**Session Pooler**, nicht Direct: Direct ist nur IPv6).

## 2. Backend (Fly.io)
```bash
cd backend
fly launch --no-deploy --copy-config --name <dein-app-name>
fly secrets set \
  DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres' \
  SUPABASE_URL='https://<ref>.supabase.co' \
  SUPABASE_SERVICE_ROLE_KEY='...' \
  GEMINI_API_KEY='...' \
  FRONTEND_URL='https://app.deinedomain.de' \
  CORS_ORIGINS='["https://app.deinedomain.de"]'
fly deploy
curl https://<dein-app-name>.fly.dev/health   # -> {"status":"ok"}
```
JWT-Prüfung: Projekte mit asymmetrischen Signing Keys brauchen nur `SUPABASE_URL`. Hat dein Projekt noch das alte JWT-Secret, setze zusätzlich `SUPABASE_JWT_SECRET` (nur dann!).
Railway/Render: Dockerfile in `backend/` verwenden, dieselben Variablen setzen, Health-Check `/health`.

## 3. Frontend (Vercel)
1. Repo importieren, *Root Directory* = `web`.
2. Variablen: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL=https://<dein-app-name>.fly.dev`.
3. Deploy. Danach die Vercel-URL bei Supabase (Site/Redirect URL) und im Backend (`FRONTEND_URL`, `CORS_ORIGINS`) eintragen.

## 4. Checkliste vor dem ersten Kunden
- [ ] Gemini-Key neu erzeugt (der alte stand im Chat) und in der Cloud Console auf die Generative-Language-API beschränkt
- [ ] `service_role`-Key nur als Backend-Secret, nirgends im Frontend/Git
- [ ] Test: Registrieren → Firma anlegen → Projekt → Stunden → Beleg scannen → Ampel
- [ ] Test: zweiter Account einer anderen Firma sieht keine fremden Projekte (Mandantentrennung)
- [ ] Einladung testen: Mail kommt an, Passwort setzen klappt, Mitarbeiter sieht keine Löschen-Rechte fremder Buchungen
- [ ] AVV/Datenschutz: Belege gehen an Google (Gemini) – in der Datenschutzerklärung aufführen und AV-Vertrag prüfen
- [ ] Impressum/AGB/Datenschutz im Frontend verlinken
