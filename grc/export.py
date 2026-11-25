"""Audit-ready exports: Excel workbook (register, SoA, audit log, summary) and CSV."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .ai_engine import AI_FLAG
from .controls import ANNEX_A, theme_of
from .scoring import RATING_COLOURS

REGISTER_COLS = {
    "risk_ref": "Risk ID", "asset": "Asset", "threat": "Threat", "vulnerability": "Vulnerability",
    "owner": "Risk Owner", "likelihood": "Likelihood", "impact": "Impact",
    "inherent_score": "Inherent Score", "inherent_rating": "Inherent Rating",
    "treatment": "Treatment", "controls_str": "Annex A Controls", "treatment_plan": "Treatment Plan",
    "residual_likelihood": "Residual L", "residual_impact": "Residual I",
    "residual_score": "Residual Score", "residual_rating": "Residual Rating",
    "ai_source": "Suggestion Source", "status": "Validation Status",
    "validated_by": "Validated By", "validated_at": "Validated At", "ai_rationale": "AI Rationale",
}


def register_table(risks: pd.DataFrame) -> pd.DataFrame:
    if risks.empty:
        return pd.DataFrame(columns=list(REGISTER_COLS.values()))
    df = risks.copy()
    df["controls_str"] = df["controls"].apply(lambda c: ", ".join(f"A.{x}" for x in c))
    return df[list(REGISTER_COLS)].rename(columns=REGISTER_COLS)


def soa_table(risks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cid, name in ANNEX_A.items():
        linked = []
        if not risks.empty:
            linked = risks[risks["controls"].apply(lambda c: cid in c)]["risk_ref"].tolist()
        rows.append({
            "Control": f"A.{cid}", "Title": name, "Theme": theme_of(cid),
            "Applicable": "Yes" if linked else "Review",
            "Justification": f"Treats {', '.join(linked)}" if linked else
                             "Not linked to an assessed risk - confirm applicability",
            "Linked Risks": len(linked),
        })
    return pd.DataFrame(rows)


def summary_table(risks: pd.DataFrame) -> pd.DataFrame:
    n = len(risks)
    val = int((risks["status"] == "Validated").sum()) if n else 0
    return pd.DataFrame([
        ("Report generated", datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Standard", "ISO/IEC 27001:2022 (Clause 6.1.2 risk assessment, 6.1.3 treatment)"),
        ("Total risks", n),
        ("Human-validated", val),
        ("Awaiting validation", n - val if n else 0),
        ("Average inherent score", round(risks["inherent_score"].mean(), 1) if n else 0),
        ("Average residual score", round(risks["residual_score"].mean(), 1) if n else 0),
        ("Notice", f"Rows marked '{AI_FLAG}' are AI-generated proposals and are NOT approved "
                   "until a named person validates them."),
    ], columns=["Item", "Value"])


def _style(ws, df):
    head = PatternFill("solid", fgColor="0C231D")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFAD0", name="Consolas")
        c.fill = head
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for i, col in enumerate(df.columns, 1):
        lens = df[col].fillna("").astype(str).str.len() if len(df) else pd.Series([12])
        width = min(60, max(12, int(lens.quantile(0.9) or 12)))
        ws.column_dimensions[get_column_letter(i)].width = max(width, len(str(col)) + 2)
        for cell in ws.iter_rows(min_row=2, min_col=i, max_col=i):
            cell[0].alignment = Alignment(wrap_text=True, vertical="top")
            v = str(cell[0].value)
            if v in RATING_COLOURS:
                cell[0].fill = PatternFill("solid", fgColor=RATING_COLOURS[v].lstrip("#"))
                cell[0].font = Font(bold=True, color="0C231D")
            elif v == AI_FLAG:
                cell[0].fill = PatternFill("solid", fgColor="FFFAD0")
    ws.freeze_panes = "B2"


def to_excel(risks: pd.DataFrame, audit: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    sheets = {"Summary": summary_table(risks), "Risk Register": register_table(risks),
              "Statement of Applicability": soa_table(risks),
              "Audit Log": audit.rename(columns=str.title)}
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            _style(xw.sheets[name], df)
    return buf.getvalue()


def to_csv(risks: pd.DataFrame) -> bytes:
    return register_table(risks).to_csv(index=False).encode("utf-8-sig")
