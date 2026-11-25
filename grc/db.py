"""SQLite persistence for the risk register and the audit trail."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from .ai_engine import AI_FLAG
from .scoring import score, rating

DEFAULT_DB = Path(os.getenv("GRC_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "grc.db"))

STATUS_PENDING = AI_FLAG
STATUS_VALIDATED = "Validated"
STATUS_REJECTED = "Rejected"

SCHEMA = """
CREATE TABLE IF NOT EXISTS risks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_ref TEXT UNIQUE,
    asset TEXT NOT NULL,
    threat TEXT NOT NULL,
    vulnerability TEXT NOT NULL,
    description TEXT,
    owner TEXT,
    likelihood INTEGER NOT NULL,
    impact INTEGER NOT NULL,
    inherent_score INTEGER NOT NULL,
    treatment TEXT,
    controls TEXT,
    treatment_plan TEXT,
    residual_likelihood INTEGER NOT NULL,
    residual_impact INTEGER NOT NULL,
    residual_score INTEGER NOT NULL,
    ai_source TEXT,
    ai_rationale TEXT,
    status TEXT NOT NULL,
    validated_by TEXT,
    validated_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    risk_ref TEXT,
    details TEXT
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path or DEFAULT_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def log(conn, actor: str, action: str, risk_ref: str | None = None, details: str = "") -> None:
    conn.execute("INSERT INTO audit_log (ts, actor, action, risk_ref, details) VALUES (?,?,?,?,?)",
                 (now(), actor, action, risk_ref, details))
    conn.commit()


def _next_ref(conn) -> str:
    row = conn.execute("SELECT MAX(id) FROM risks").fetchone()
    return f"R-{(row[0] or 0) + 1:03d}"


def add_risk(conn, *, asset, threat, vulnerability, description="", owner="",
             suggestion=None, actor="system", **manual) -> str:
    """Insert a risk. If `suggestion` (ai_engine.Suggestion) is given it is stored
    with status 'AI Suggestion – Human Validation Required'."""
    ref = _next_ref(conn)
    if suggestion is not None:
        s = suggestion
        vals = dict(likelihood=s.likelihood, impact=s.impact, treatment=s.treatment,
                    controls=s.controls, treatment_plan=s.treatment_plan,
                    residual_likelihood=s.residual_likelihood, residual_impact=s.residual_impact,
                    ai_source=s.source, ai_rationale=s.rationale, status=STATUS_PENDING)
    else:
        vals = dict(likelihood=manual.get("likelihood", 3), impact=manual.get("impact", 3),
                    treatment=manual.get("treatment", "Mitigate"),
                    controls=manual.get("controls", []),
                    treatment_plan=manual.get("treatment_plan", ""),
                    residual_likelihood=manual.get("residual_likelihood", 2),
                    residual_impact=manual.get("residual_impact", 2),
                    ai_source="manual", ai_rationale="", status=STATUS_VALIDATED)
    ts = now()
    conn.execute(
        """INSERT INTO risks (risk_ref, asset, threat, vulnerability, description, owner,
           likelihood, impact, inherent_score, treatment, controls, treatment_plan,
           residual_likelihood, residual_impact, residual_score, ai_source, ai_rationale,
           status, validated_by, validated_at, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ref, asset, threat, vulnerability, description, owner,
         vals["likelihood"], vals["impact"], score(vals["likelihood"], vals["impact"]),
         vals["treatment"], json.dumps(vals["controls"]), vals["treatment_plan"],
         vals["residual_likelihood"], vals["residual_impact"],
         score(vals["residual_likelihood"], vals["residual_impact"]),
         vals["ai_source"], vals["ai_rationale"], vals["status"],
         actor if vals["status"] == STATUS_VALIDATED else None,
         ts if vals["status"] == STATUS_VALIDATED else None, ts, ts))
    conn.commit()
    action = "AI_SUGGESTION_CREATED" if suggestion is not None else "RISK_CREATED_MANUAL"
    log(conn, actor, action, ref, f"source={vals['ai_source']}; inherent="
        f"{score(vals['likelihood'], vals['impact'])}; residual="
        f"{score(vals['residual_likelihood'], vals['residual_impact'])}")
    return ref


def update_risk(conn, risk_ref: str, actor: str, **fields) -> None:
    allowed = {"asset", "threat", "vulnerability", "description", "owner", "likelihood", "impact",
               "treatment", "controls", "treatment_plan", "residual_likelihood", "residual_impact"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    if "controls" in fields and not isinstance(fields["controls"], str):
        fields["controls"] = json.dumps(list(fields["controls"]))
    cur = get_risk(conn, risk_ref)
    merged = {**cur, **fields}
    fields["inherent_score"] = score(merged["likelihood"], merged["impact"])
    fields["residual_score"] = score(merged["residual_likelihood"], merged["residual_impact"])
    fields["updated_at"] = now()
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE risks SET {sets} WHERE risk_ref=?", (*fields.values(), risk_ref))
    conn.commit()
    changed = ", ".join(f"{k}={v}" for k, v in fields.items() if k != "updated_at")
    log(conn, actor, "RISK_EDITED", risk_ref, changed)


def set_status(conn, risk_ref: str, status: str, actor: str, comment: str = "") -> None:
    if not actor or not actor.strip():
        raise ValueError("A named validator is required")
    conn.execute("UPDATE risks SET status=?, validated_by=?, validated_at=?, updated_at=? "
                 "WHERE risk_ref=?", (status, actor, now(), now(), risk_ref))
    conn.commit()
    log(conn, actor, "HUMAN_VALIDATED" if status == STATUS_VALIDATED else "HUMAN_REJECTED",
        risk_ref, comment)


def delete_risk(conn, risk_ref: str, actor: str) -> None:
    conn.execute("DELETE FROM risks WHERE risk_ref=?", (risk_ref,))
    conn.commit()
    log(conn, actor, "RISK_DELETED", risk_ref, "")


def get_risk(conn, risk_ref: str) -> dict:
    row = conn.execute("SELECT * FROM risks WHERE risk_ref=?", (risk_ref,)).fetchone()
    return dict(row) if row else {}


def risks_df(conn) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM risks ORDER BY id", conn)
    if not df.empty:
        df["controls"] = df["controls"].apply(lambda s: json.loads(s) if s else [])
        df["inherent_rating"] = df["inherent_score"].apply(rating)
        df["residual_rating"] = df["residual_score"].apply(rating)
    return df


def audit_df(conn) -> pd.DataFrame:
    return pd.read_sql_query("SELECT ts, actor, action, risk_ref, details FROM audit_log "
                             "ORDER BY id DESC", conn)


def reset(conn) -> None:
    conn.executescript("DELETE FROM risks; DELETE FROM audit_log; "
                       "DELETE FROM sqlite_sequence WHERE name IN ('risks','audit_log');")
    conn.commit()
