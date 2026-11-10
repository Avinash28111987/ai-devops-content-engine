# AI DevOps Content Engine

A local-first MVP that turns one topic into a LinkedIn post, Instagram caption, short-form video script and storyboard, hashtags, and a call to action. Content is saved to SQLite on your Mac or PostgreSQL when hosted. The queue tracks `DRAFT`, `APPROVED`, and `PUBLISHED`; publishing to social platforms is not connected.

## Run it on your Mac

Requires Python 3.10 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. Sign in with `admin` / `local-dev-password` (change these in `.env` for your own use). The sample topic **AI agents in CI/CD pipelines** is prefilled. Data is stored in `data/content.db`.

## Put it online free (Render + Supabase)

Render runs the website. Supabase stores the posts safely in a hosted database. You need free accounts on both services and a GitHub repository containing this project.

### 1. Save this project in GitHub

Create a private GitHub repository and upload the contents of this project folder. Keep `.env` and `.venv` out of Git; `.gitignore` already excludes them. You do not need to upload your API key or password.

### 2. Create the free database

In Supabase, create a project. Open **Connect** and copy its PostgreSQL connection string. Keep it private; you will paste it into Render in a later step. Supabase Free currently includes a 500 MB database and may pause projects after a week of very low activity.

### 3. Create the free website

In Render, choose **New → Web Service**, connect the GitHub repository, and set:

- **Root Directory:** `ai-devops-content-engine` (if this folder is inside a larger repository)
- **Runtime:** Python
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Instance Type:** Free

If the GitHub repository contains only this project, leave **Root Directory** blank.

### 4. Add the private settings in Render

Open the service's **Environment** settings and add:

| Name | Value |
|---|---|
| `DATABASE_URL` | The PostgreSQL connection string from Supabase |
| `BASIC_AUTH_USER` | A username you choose |
| `BASIC_AUTH_PASSWORD` | A long, unique password |
| `LLM_PROVIDER` | `local` to start without an AI key |

To use your enterprise AI endpoint later, also add `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`. Save the settings and deploy. Render will show the website address when deployment finishes. Sign in with the username and password you chose.

Keep those values in Render's Environment settings; do not put them in a public file or GitHub. `DATABASE_URL` enables PostgreSQL mode. Without it, the app uses local SQLite.

## Free hosting limits

The website may take about a minute to wake after 15 minutes without visitors. Supabase may pause a free database after seven days of very low activity; it can be resumed from its dashboard. These services are suitable for trying the app with light usage, not for a service that must always be available.

## API

- `GET /api/health` — service status (public)
- `GET /api/content` — saved content (login required)
- `POST /api/content` — generate and save a draft (login required)
- `PATCH /api/content/{id}/status` — set `DRAFT`, `APPROVED`, or `PUBLISHED` (login required)
- `GET /docs` — API reference (data routes still require login)

## Project layout

```text
app/
  content.py       local and enterprise LLM generation
  main.py          FastAPI routes, login, SQLite/PostgreSQL storage
  static/index.html
requirements.txt
.env.example
```
