"""Automated tests for GRC.AI.  Run:  python -m pytest -v"""
import io
import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from grc import db  # noqa: E402
from grc.ai_engine import AI_FLAG, rule_engine, suggest, validate_model_output  # noqa: E402
from grc.controls import ANNEX_A  # noqa: E402
from grc.export import soa_table, to_csv, to_excel  # noqa: E402
from grc.scoring import rating, score  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    return db.connect(tmp_path / "test.db")


def test_annex_a_has_93_controls():
    assert len(ANNEX_A) == 93
    themes = [c.split(".")[0] for c in ANNEX_A]
    assert themes.count("5") == 37 and themes.count("6") == 8
    assert themes.count("7") == 14 and themes.count("8") == 34


def test_scoring_and_rating():
    assert score(4, 5) == 20 and rating(20) == "Critical"
    assert rating(12) == "High" and rating(6) == "Medium" and rating(4) == "Low"


def test_rule_engine_remote_access_without_mfa():
    s = rule_engine("VPN", "credential stuffing", "Remote access without MFA")
    assert (s.inherent_score, s.residual_score) == (20, 8)
    assert "8.5" in s.controls and s.flag == AI_FLAG


def test_rule_engine_stale_accounts():
    s = rule_engine("AD", "misuse", "Stale accounts not disabled after offboarding")
    assert "5.18" in s.controls and "6.5" in s.controls


def test_offline_suggest_when_no_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert suggest("x", "phishing", "no awareness").source == "rule-engine"


def test_gemini_failure_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "invalid-key-for-test")
    import grc.ai_engine as eng
    monkeypatch.setattr(eng, "gemini_engine", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    s = eng.suggest("VPN", "attack", "remote access without MFA")
    assert s.source == "rule-engine" and "Gemini unavailable" in s.rationale


def test_model_output_guardrails():
    s = validate_model_output({"likelihood": 9, "impact": 0, "controls": ["A.8.5", "99.9", "8.5"],
                               "residual_likelihood": 5, "residual_impact": 5,
                               "treatment": "ignore"}, "gemini")
    assert (s.likelihood, s.impact) == (5, 1)
    assert s.controls == ["8.5"]                      # invalid + duplicate removed
    assert s.residual_impact <= s.impact               # residual never above inherent
    assert s.treatment == "Mitigate"
    with pytest.raises(ValueError):
        validate_model_output({"controls": ["1.1"]}, "gemini")


def test_ai_suggestion_requires_validation(conn):
    ref = db.add_risk(conn, asset="VPN", threat="t", vulnerability="remote access without MFA",
                      suggestion=rule_engine("VPN", "t", "remote access without MFA"))
    assert db.get_risk(conn, ref)["status"] == AI_FLAG
    with pytest.raises(ValueError):
        db.set_status(conn, ref, db.STATUS_VALIDATED, "  ")
    db.set_status(conn, ref, db.STATUS_VALIDATED, "Jane CISO", "ok")
    r = db.get_risk(conn, ref)
    assert r["status"] == "Validated" and r["validated_by"] == "Jane CISO"
    actions = db.audit_df(conn).action.tolist()
    assert "AI_SUGGESTION_CREATED" in actions and "HUMAN_VALIDATED" in actions


def test_edit_recalculates_scores(conn):
    ref = db.add_risk(conn, asset="a", threat="t", vulnerability="v", likelihood=2, impact=2)
    db.update_risk(conn, ref, "tester", likelihood=5, impact=5, residual_likelihood=1)
    r = db.get_risk(conn, ref)
    assert r["inherent_score"] == 25 and r["residual_score"] == 2


def test_sample_run_12_to_6_2(conn):
    samples = json.loads((ROOT / "data" / "sample_risks.json").read_text("utf-8"))
    for s in samples:
        db.add_risk(conn, suggestion=suggest(s["asset"], s["threat"], s["vulnerability"],
                                             s["description"], use_gemini=False), **s)
    df = db.risks_df(conn)
    assert len(df) == 10
    assert round(df.inherent_score.mean(), 1) == 12.0
    assert round(df.residual_score.mean(), 1) == 6.2


def test_exports(conn):
    db.add_risk(conn, asset="VPN", threat="t", vulnerability="remote access without MFA",
                suggestion=rule_engine("VPN", "t", "remote access without MFA"))
    df = db.risks_df(conn)
    xls = pd.read_excel(io.BytesIO(to_excel(df, db.audit_df(conn))), sheet_name=None)
    assert set(xls) == {"Summary", "Risk Register", "Statement of Applicability", "Audit Log"}
    assert len(xls["Statement of Applicability"]) == 93
    assert xls["Risk Register"].iloc[0]["Validation Status"] == AI_FLAG
    assert b"Risk ID" in to_csv(df)
    assert (soa_table(df).Applicable == "Yes").sum() == 5


def test_streamlit_app_pages(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("GRC_DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import importlib
    importlib.reload(db)
    for page in ["Dashboard", "Assess New Risk", "Risk Register", "Annex A Controls",
                 "Export", "Audit Log"]:
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, f"{page}: {at.exception}"


def test_ui_assess_save_validate_flow(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("GRC_DB_PATH", str(tmp_path / "flow.db"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import importlib
    importlib.reload(db)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    at.sidebar.radio[0].set_value("Assess New Risk").run()
    ti = {t.label: t for t in at.text_input}
    ti["Asset *"].set_value("VPN gateway")
    ti["Threat *"].set_value("Credential stuffing")
    ti["Vulnerability *"].set_value("Remote access without MFA")
    next(b for b in at.button if "get AI suggestion" in b.label).click().run()
    assert any(AI_FLAG in w.value for w in at.warning)
    next(b for b in at.button if b.label.startswith("save to register")).click().run()
    assert any("Saved as R-001" in s.value for s in at.success)
    at.sidebar.radio[0].set_value("Risk Register").run()
    next(b for b in at.button if b.label == "validate").click().run()
    conn = db.connect(tmp_path / "flow.db")
    assert db.get_risk(conn, "R-001")["status"] == "Validated"


def test_gemini_engine_with_mocked_client(monkeypatch):
    """Exercises the Gemini code path without a network call."""
    from google import genai
    from google.genai import types

    class FakeModels:
        def generate_content(self, model, contents, config):
            types.GenerateContentConfig(**config)   # config must be valid for the real SDK
            assert "Remote access without MFA" in contents

            class R:
                text = json.dumps({"likelihood": 4, "impact": 5, "treatment": "Mitigate",
                                   "controls": ["8.5", "5.17", "6.7"], "treatment_plan": "MFA",
                                   "residual_likelihood": 2, "residual_impact": 4,
                                   "rationale": "Password-only remote access."})
            return R()

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    s = suggest("VPN", "credential stuffing", "Remote access without MFA")
    assert s.source.startswith("gemini") and s.inherent_score == 20 and s.residual_score == 8
