from __future__ import annotations

import json
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

load_dotenv()

from .content import generate_content

DB_PATH = Path(os.getenv("DATABASE_PATH", "./data/content.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
VALID_STATUSES = {"DRAFT", "APPROVED", "PUBLISHED"}
basic_auth = HTTPBasic()


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    audience: str = Field(default="DevOps engineers and cloud architects", max_length=250)
    tone: str = Field(default="practical", max_length=100)


class PostgresConnection:
    """Small compatibility wrapper so local and hosted databases share queries."""
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.__enter__()
        return self

    def __exit__(self, *args):
        return self.connection.__exit__(*args)

    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace("?", "%s"), params)


def connect():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row
        parsed = urlparse(DATABASE_URL)
        query = parsed.query
        if "sslmode=" not in query:
            query = f"{query}&sslmode=require" if query else "sslmode=require"
        return PostgresConnection(psycopg.connect(urlunparse(parsed._replace(query=query)), row_factory=dict_row))
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def initialize() -> None:
    identity = "BIGSERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with connect() as db:
        db.execute(f"""CREATE TABLE IF NOT EXISTS content (
            id {identity}, topic TEXT NOT NULL, audience TEXT NOT NULL,
            tone TEXT NOT NULL, linkedin_post TEXT NOT NULL, instagram_caption TEXT NOT NULL,
            reel_script TEXT NOT NULL, storyboard TEXT NOT NULL, hashtags TEXT NOT NULL, cta TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'DRAFT', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    yield


app = FastAPI(title="AI DevOps Content Engine", version="0.2.0", lifespan=lifespan)


def require_login(credentials: HTTPBasicCredentials = Depends(basic_auth)) -> str:
    expected_user = os.getenv("BASIC_AUTH_USER", "admin").strip()
    expected_password = os.getenv("BASIC_AUTH_PASSWORD", "local-dev-password")
    if DATABASE_URL and (not os.getenv("BASIC_AUTH_USER") or not os.getenv("BASIC_AUTH_PASSWORD")):
        raise HTTPException(status_code=503, detail="Set BASIC_AUTH_USER and BASIC_AUTH_PASSWORD before using the hosted app")
    if not expected_user or not expected_password:
        raise HTTPException(status_code=503, detail="Set BASIC_AUTH_USER and BASIC_AUTH_PASSWORD before using the app")
    good_user = secrets.compare_digest(credentials.username, expected_user)
    good_password = secrets.compare_digest(credentials.password, expected_password)
    if not (good_user and good_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def serialize(row) -> dict:
    item = dict(row)
    item["storyboard"] = json.loads(item["storyboard"])
    item["hashtags"] = json.loads(item["hashtags"])
    return item


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/content", dependencies=[Depends(require_login)])
def list_content() -> list[dict]:
    with connect() as db:
        rows = db.execute("SELECT * FROM content ORDER BY created_at DESC, id DESC").fetchall()
    return [serialize(row) for row in rows]


@app.post("/api/content", status_code=201, dependencies=[Depends(require_login)])
def create_content(request: GenerateRequest) -> dict:
    try:
        generated = generate_content(request.topic, request.audience, request.tone)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    now = datetime.now(timezone.utc).isoformat()
    sql = """INSERT INTO content (topic, audience, tone, linkedin_post, instagram_caption,
        reel_script, storyboard, hashtags, cta, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?)"""
    with connect() as db:
        if DATABASE_URL:
            sql += " RETURNING id"
        cursor = db.execute(sql, (request.topic.strip(), request.audience, request.tone,
            generated["linkedin_post"], generated["instagram_caption"], generated["reel_script"],
            json.dumps(generated["storyboard"]), json.dumps(generated["hashtags"]), generated["cta"], now, now))
        content_id = cursor.fetchone()["id"] if DATABASE_URL else cursor.lastrowid
        row = db.execute("SELECT * FROM content WHERE id = ?", (content_id,)).fetchone()
    return serialize(row)


@app.patch("/api/content/{content_id}/status", dependencies=[Depends(require_login)])
def update_status(content_id: int, body: dict) -> dict:
    status = body.get("status")
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="Status must be DRAFT, APPROVED, or PUBLISHED")
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        cursor = db.execute("UPDATE content SET status = ?, updated_at = ? WHERE id = ?", (status, now, content_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Content not found")
        row = db.execute("SELECT * FROM content WHERE id = ?", (content_id,)).fetchone()
    return serialize(row)


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_login)])
def home() -> str:
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
