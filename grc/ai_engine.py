"""AI suggestion engine.

* If GEMINI_API_KEY is set, Google Gemini proposes likelihood, impact,
  treatment, Annex A controls and residual scores (JSON mode).
* If no key is set, or Gemini fails / returns invalid output, a local
  rule-based engine produces the suggestion so the tool works offline.

Every suggestion is labelled "AI Suggestion - Human Validation Required"
and must be validated by a named person before it counts as approved.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict

from .controls import ANNEX_A, is_valid
from .scoring import clamp, score, TREATMENTS

AI_FLAG = "AI Suggestion – Human Validation Required"


@dataclass
class Suggestion:
    likelihood: int
    impact: int
    treatment: str
    controls: list = field(default_factory=list)
    treatment_plan: str = ""
    residual_likelihood: int = 1
    residual_impact: int = 1
    rationale: str = ""
    source: str = "rule-engine"
    flag: str = AI_FLAG

    @property
    def inherent_score(self) -> int:
        return score(self.likelihood, self.impact)

    @property
    def residual_score(self) -> int:
        return score(self.residual_likelihood, self.residual_impact)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["inherent_score"] = self.inherent_score
        d["residual_score"] = self.residual_score
        return d


# --------------------------------------------------------------------------
# Offline rule engine
# --------------------------------------------------------------------------
RULES = [
    {
        "name": "Remote access without MFA",
        "keywords": ["remote access", "vpn", "rdp", "without mfa", "no mfa", "single-factor",
                     "multi-factor", "mfa"],
        "L": 4, "I": 5, "RL": 2, "RI": 4, "treatment": "Mitigate",
        "controls": ["8.5", "5.17", "8.20", "6.7", "8.16"],
        "plan": "Enforce MFA on all remote-access paths (VPN, RDP gateway, SaaS admin), "
                "block legacy authentication, alert on impossible-travel and repeated failures.",
    },
    {
        "name": "Stale accounts after offboarding",
        "keywords": ["stale", "offboard", "leaver", "orphan", "terminated", "dormant",
                     "post-offboarding", "former employee", "not disabled"],
        "L": 4, "I": 4, "RL": 2, "RI": 4, "treatment": "Mitigate",
        "controls": ["5.18", "6.5", "5.16", "8.2", "5.11"],
        "plan": "Link HR leaver feed to IAM so accounts are disabled on the last working day; "
                "run monthly access reviews and quarterly dormant-account sweeps (>30 days).",
    },
    {
        "name": "Unpatched / vulnerable systems",
        "keywords": ["unpatched", "patch", "vulnerab", "outdated", "end-of-life", "eol", "cve"],
        "L": 3, "I": 5, "RL": 2, "RI": 3, "treatment": "Mitigate",
        "controls": ["8.8", "8.9", "8.19", "8.7"],
        "plan": "Monthly patch cycle with 14-day SLA for critical CVEs, authenticated "
                "vulnerability scanning and a hardened configuration baseline.",
    },
    {
        "name": "Backup / ransomware resilience",
        "keywords": ["backup", "ransomware", "restore", "recovery"],
        "L": 3, "I": 4, "RL": 2, "RI": 3, "treatment": "Mitigate",
        "controls": ["8.13", "8.7", "5.30", "8.14"],
        "plan": "3-2-1 backups with one immutable/offline copy, quarterly restore tests and "
                "EDR with ransomware behaviour blocking.",
    },
    {
        "name": "Phishing / low awareness",
        "keywords": ["phishing", "awareness", "social engineering", "email lure", "training"],
        "L": 4, "I": 3, "RL": 2, "RI": 3, "treatment": "Mitigate",
        "controls": ["6.3", "8.23", "8.7", "6.8"],
        "plan": "Quarterly awareness training with phishing simulations, a one-click "
                "report-phish button and DNS/web filtering of newly registered domains.",
    },
    {
        "name": "Supplier / third-party risk",
        "keywords": ["vendor", "supplier", "third party", "third-party", "outsourc", "contractor"],
        "L": 2, "I": 5, "RL": 2, "RI": 3, "treatment": "Transfer",
        "controls": ["5.19", "5.20", "5.21", "5.22"],
        "plan": "Security clauses and right-to-audit in contracts, annual supplier "
                "questionnaires, cyber-insurance and breach-notification SLAs.",
    },
    {
        "name": "Insufficient logging / monitoring",
        "keywords": ["logging", "logs", "monitoring", "siem", "audit trail", "not monitored"],
        "L": 3, "I": 3, "RL": 2, "RI": 3, "treatment": "Mitigate",
        "controls": ["8.15", "8.16", "8.17", "5.25"],
        "plan": "Centralise logs in a SIEM with 12-month retention, NTP-synchronised clocks "
                "and use-case alerts reviewed daily.",
    },
    {
        "name": "Lost or stolen devices",
        "keywords": ["laptop", "lost", "stolen", "theft", "device", "off-premises"],
        "L": 2, "I": 4, "RL": 1, "RI": 4, "treatment": "Mitigate",
        "controls": ["7.9", "8.1", "8.24", "7.10"],
        "plan": "Full-disk encryption (BitLocker), MDM with remote wipe and an asset "
                "check-out register.",
    },
    {
        "name": "Data leakage / PII exposure",
        "keywords": ["data leak", "leakage", "pii", "personal data", "usb", "exfiltrat",
                     "student records", "confidential"],
        "L": 2, "I": 5, "RL": 2, "RI": 3, "treatment": "Mitigate",
        "controls": ["8.12", "5.34", "8.11", "5.12"],
        "plan": "Classify data, deploy DLP on email/USB/cloud, mask PII in non-production and "
                "complete a DPIA under the DPDP Act / GDPR.",
    },
    {
        "name": "Privileged / shared admin accounts",
        "keywords": ["privileged", "admin", "shared account", "root", "domain admin", "superuser"],
        "L": 2, "I": 4, "RL": 2, "RI": 3, "treatment": "Mitigate",
        "controls": ["8.2", "8.18", "5.3", "8.15"],
        "plan": "Named admin accounts via a PAM vault, just-in-time elevation, session "
                "recording and quarterly privileged-access recertification.",
    },
    {
        "name": "Cloud misconfiguration",
        "keywords": ["cloud", "s3", "bucket", "azure", "public storage", "misconfig"],
        "L": 3, "I": 4, "RL": 2, "RI": 3, "treatment": "Mitigate",
        "controls": ["5.23", "8.9", "8.3", "8.24"],
        "plan": "Cloud security posture management, deny-public-access guardrails and "
                "infrastructure-as-code reviews.",
    },
]

DEFAULT_RULE = {
    "name": "General information-security risk",
    "L": 3, "I": 3, "RL": 2, "RI": 2, "treatment": "Mitigate",
    "controls": ["5.1", "5.15", "8.16"],
    "plan": "Define an owner, document the control, and review effectiveness quarterly.",
}


def _match_rule(text: str) -> dict:
    t = text.lower()
    best, best_hits = None, 0
    for rule in RULES:
        hits = sum(1 for k in rule["keywords"] if k in t)
        if hits > best_hits:
            best, best_hits = rule, hits
    return best or DEFAULT_RULE


def rule_engine(asset: str, threat: str, vulnerability: str, description: str = "") -> Suggestion:
    text = " ".join([asset, threat, vulnerability, description])
    r = _match_rule(text)
    return Suggestion(
        likelihood=r["L"], impact=r["I"], treatment=r["treatment"],
        controls=list(r["controls"]), treatment_plan=r["plan"],
        residual_likelihood=r["RL"], residual_impact=r["RI"],
        rationale=f"Matched risk pattern '{r['name']}' in the offline knowledge base. "
                  f"Inherent {r['L']}x{r['I']}; after the listed Annex A controls are "
                  f"implemented, residual is estimated at {r['RL']}x{r['RI']}.",
        source="rule-engine",
    )


# --------------------------------------------------------------------------
# Gemini engine
# --------------------------------------------------------------------------
PROMPT = """You are an ISO/IEC 27001:2022 lead implementer helping a university assess risk.
Assess this risk on a 5x5 scale (1=lowest, 5=highest).

Asset: {asset}
Threat: {threat}
Vulnerability: {vulnerability}
Context: {description}

Return ONLY a JSON object with these keys:
"likelihood" (int 1-5), "impact" (int 1-5),
"treatment" (one of Mitigate, Accept, Transfer, Avoid),
"controls" (list of 2-6 ISO/IEC 27001:2022 Annex A control numbers such as "8.5", "5.18"),
"treatment_plan" (max 2 sentences),
"residual_likelihood" (int 1-5), "residual_impact" (int 1-5) after the controls are in place,
"rationale" (max 3 sentences).
"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("No JSON object in model output")
    return json.loads(m.group(0))


def gemini_engine(asset, threat, vulnerability, description="", api_key=None, model=None) -> Suggestion:
    from google import genai  # imported lazily so offline mode needs no SDK

    api_key = api_key or os.getenv("GEMINI_API_KEY")
    model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=model,
        contents=PROMPT.format(asset=asset, threat=threat, vulnerability=vulnerability,
                               description=description or "n/a"),
        config={"response_mime_type": "application/json", "temperature": 0.2},
    )
    data = _parse_json(resp.text)
    return validate_model_output(data, source=f"gemini ({model})")


def validate_model_output(data: dict, source: str) -> Suggestion:
    """Guard-rails: clamp scores, reject unknown controls, enforce residual <= inherent."""
    L, I = clamp(data.get("likelihood")), clamp(data.get("impact"))
    RL, RI = clamp(data.get("residual_likelihood")), clamp(data.get("residual_impact"))
    RL, RI = min(RL, L), min(RI, I)
    controls = []
    for c in data.get("controls", []) or []:
        c = str(c).upper().replace("A.", "").strip()
        if is_valid(c) and c not in controls:
            controls.append(c)
    if not controls:
        raise ValueError("Model returned no valid Annex A controls")
    treatment = str(data.get("treatment", "Mitigate")).title()
    if treatment not in TREATMENTS:
        treatment = "Mitigate"
    return Suggestion(
        likelihood=L, impact=I, treatment=treatment, controls=controls[:6],
        treatment_plan=str(data.get("treatment_plan", ""))[:600],
        residual_likelihood=RL, residual_impact=RI,
        rationale=str(data.get("rationale", ""))[:800], source=source,
    )


def suggest(asset: str, threat: str, vulnerability: str, description: str = "",
            use_gemini: bool | None = None) -> Suggestion:
    """Return an AI suggestion. Falls back to the rule engine on any Gemini problem."""
    if use_gemini is None:
        use_gemini = bool(os.getenv("GEMINI_API_KEY"))
    if use_gemini:
        try:
            return gemini_engine(asset, threat, vulnerability, description)
        except Exception as exc:  # network, quota, bad JSON, invalid controls ...
            s = rule_engine(asset, threat, vulnerability, description)
            s.rationale = f"[Gemini unavailable: {type(exc).__name__}] " + s.rationale
            return s
    return rule_engine(asset, threat, vulnerability, description)


def control_names(ids) -> list[str]:
    return [f"A.{c} {ANNEX_A[c]}" for c in ids if c in ANNEX_A]
