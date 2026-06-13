# Substack Notes Scheduler

A personal dashboard to **pre-plan Substack Notes** and have them **post automatically**
at scheduled times. Import a `.txt` of notes → review/edit/schedule them → they post
themselves. (Full articles you still publish manually — this tool is Notes-only.)

## How it works (and the one important caveat)

Substack has **no official API** and **no API-level scheduling**. This app posts Notes by
calling Substack's private web endpoint (`/api/v1/comment/feed`) using **your browser
session cookie**, and runs its own background scheduler to fire notes at the right time.

> Because *this app* must be running when a note is due, it's meant to run on an
> always-on host (Railway). On startup it also runs a **catch-up pass** so a brief
> restart/redeploy never drops an overdue note (it posts overdue ones immediately).

## Project layout

```
backend/    FastAPI + APScheduler + SQLite  (the API, scheduler, Substack client)
frontend/   Vite + React + Tailwind dashboard (builds into backend/static)
Dockerfile  Multi-stage build → single container
railway.json
```

## Run locally (development)

Two terminals:

```bash
# 1) Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DB_PATH=./data/notes.db SECRET_KEY=dev-secret .venv/bin/uvicorn app.main:app --port 8099 --reload

# 2) Frontend (proxies /api -> :8099)
cd frontend
npm install
npm run dev      # open http://localhost:5173
```

## Run locally as one container (production-like)

```bash
docker build -t notes-scheduler .
docker run -p 8000:8000 \
  -e SECRET_KEY="a-long-random-string" \
  -e APP_PASSWORD="your-dashboard-password" \
  -v "$PWD/data:/data" \
  notes-scheduler
# open http://localhost:8000
```

## Deploy to Railway

1. Push this repo to GitHub and create a Railway project from it (it auto-detects the Dockerfile).
2. Add a **Volume** mounted at `/data` (so the SQLite DB survives redeploys).
3. Set environment variables:
   | Variable | Purpose |
   |---|---|
   | `SECRET_KEY` | Long random string. Encrypts your stored cookie — **keep it stable**, or the saved cookie can't be decrypted after a restart. |
   | `APP_PASSWORD` | Password to open the dashboard (it's publicly reachable). |
   | `DB_PATH` | `/data/notes.db` |
4. Deploy. Open the URL, enter `APP_PASSWORD`, go to **Settings**, and paste your cookie.

## Connecting your Substack account

Substack sessions are **scoped per-domain**, so the app talks to *your publication's*
host, not `substack.com`. In **Settings** you set two things:

1. **Publication URL** — where you log in. If you have a custom domain use that
   (e.g. `https://www.tomdev.blog`); otherwise `https://yourname.substack.com`.
2. **Session cookie**:
   1. Log in to **your publication** in the browser.
   2. Open DevTools (F12) → **Network** tab, type `api` in the filter.
   3. Reload, then click any request to your domain's `/api/v1/...`.
   4. Under **Request Headers**, copy the entire `Cookie:` value — it must contain
      `connect.sid` (the session). A cookie grabbed while logged *out* is anonymous
      and won't work.
   5. Paste both into Settings and Save. The header shows **● Substack connected**
      when it authenticates. Re-paste whenever it drops (sessions expire periodically;
      `connect.sid` typically lasts ~3 months).

Before posting each note the app does a warm-up request that refreshes Substack's
short-lived Cloudflare cookie, so scheduled posts keep working long after you paste.

## Daily use

1. **Import** — drop a `.txt` (notes separated by **two blank lines**; a single blank
   line is kept as a paragraph break inside a note). Notes are **auto-scheduled**
   into your daily posting slots (default **09:00 & 15:00 Africa/Johannesburg**), continuing
   into the next free days after anything already scheduled. Past and already-used slots are
   skipped, so repeated imports keep flowing forward.
2. **Board** — every scheduled note stays editable until it posts: tweak the text or time
   inline, or delete it. (Drafts created manually still use **Approve & schedule** / **Auto-spread**.)
3. The scheduler posts each note at its time; posted notes link out to Substack.
   Failures show an inline error (e.g. expired cookie) and never silently retry.

Change the posting times and timezone in **Settings → Daily posting times** (comma-separated
24h times, e.g. `09:00,15:00`).

## Notes & limits

- A posted Note **can't be edited or unsent** — the review-before-approve step is the safety net.
- The private endpoint is unofficial and could change; it's isolated in
  `backend/app/substack_client.py` so any fix is one file.
