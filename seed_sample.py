"""Load the 10 sample university risks, generate AI suggestions and (optionally)
mark them as validated by a demo reviewer.

    python seed_sample.py            # suggestions stay 'AI Suggestion – Human Validation Required'
    python seed_sample.py --validate # also simulates human validation
    python seed_sample.py --offline  # force the offline rule engine even if a Gemini key exists
"""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from grc import db
from grc.ai_engine import suggest

load_dotenv()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true", help="simulate human validation")
    ap.add_argument("--offline", action="store_true", help="force the offline rule engine")
    ap.add_argument("--db", default=None, help="path to SQLite DB (default data/grc.db)")
    args = ap.parse_args()

    conn = db.connect(args.db)
    db.reset(conn)
    samples = json.loads((Path(__file__).parent / "data" / "sample_risks.json").read_text("utf-8"))
    for s in samples:
        sug = suggest(s["asset"], s["threat"], s["vulnerability"], s["description"],
                      use_gemini=False if args.offline else None)
        ref = db.add_risk(conn, suggestion=sug, actor="seed_sample.py", **s)
        if args.validate:
            db.set_status(conn, ref, db.STATUS_VALIDATED, "Demo Reviewer (CISO)",
                          "Sample run: reviewed and accepted")

    df = db.risks_df(conn)
    print(df[["risk_ref", "asset", "inherent_score", "residual_score", "ai_source", "status"]]
          .to_string(index=False))
    print(f"\nAverage inherent risk : {df.inherent_score.mean():.1f}")
    print(f"Average residual risk : {df.residual_score.mean():.1f}")


if __name__ == "__main__":
    main()
