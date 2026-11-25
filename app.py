"""GRC.AI - AI-assisted ISO/IEC 27001:2022 risk assessment tool (Streamlit UI).

Run:  streamlit run app.py
"""
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from grc import db
from grc.ai_engine import AI_FLAG, control_names, suggest
from grc.controls import ANNEX_A, THEMES, theme_of
from grc.export import register_table, soa_table, to_csv, to_excel
from grc.scoring import IMPACT, LIKELIHOOD, RATING_COLOURS, RISK_APPETITE, TREATMENTS, rating, score

import afep_theme as T

load_dotenv()
st.set_page_config(page_title="GRC.AI - ISO 27001 Risk Assessment", page_icon="◆", layout="wide")
T.streamlit_setup(st, "", "", "", show_hero=False)


@st.cache_resource
def get_conn(path: str):
    return db.connect(path or None)


conn = get_conn(os.getenv("GRC_DB_PATH", ""))
GEMINI_ON = bool(os.getenv("GEMINI_API_KEY"))

# ------------------------------------------------------------------ sidebar
st.sidebar.markdown("<div class='afep-eyebrow'>project</div><h3 style='margin:0'>GRC.AI</h3>"
                    "<p class='afep-foot'>AI-ASSISTED ISO/IEC 27001:2022 RISK ASSESSMENT</p>",
                    unsafe_allow_html=True)
page = st.sidebar.radio("Navigate", ["Dashboard", "Assess New Risk", "Risk Register",
                                     "Annex A Controls", "Export", "Audit Log"])
user = st.sidebar.text_input("Your name (recorded in audit trail)", value="Risk Analyst")
st.sidebar.markdown("---")
if GEMINI_ON:
    st.sidebar.markdown(f"<span class='afep-tag'>[ engine: gemini · {os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')} ]"
                        "</span>", unsafe_allow_html=True)
else:
    st.sidebar.markdown("<span class='afep-tag'>[ engine: offline rules ]</span>", unsafe_allow_html=True)
    st.sidebar.caption("Add GEMINI_API_KEY to .env to use Gemini.")

with st.sidebar.expander("Sample data / reset"):
    if st.button("Load 10 sample university risks"):
        samples = json.loads((Path(__file__).parent / "data" / "sample_risks.json").read_text("utf-8"))
        db.reset(conn)
        with st.spinner("Generating AI suggestions..."):
            for s in samples:
                sug = suggest(s["asset"], s["threat"], s["vulnerability"], s["description"])
                db.add_risk(conn, suggestion=sug, actor=user, **s)
        st.success("Loaded. Validate them in the Risk Register.")
    if st.button("Delete ALL data", type="secondary"):
        db.reset(conn)
        db.log(conn, user, "REGISTER_RESET")
        st.warning("Register cleared.")

df = db.risks_df(conn)


def ai_banner():
    st.warning(f"**[!] {AI_FLAG}** — the scores, treatment and controls below were proposed by "
               "AI. They are not approved until a named person validates them.")


def heatmap(data: pd.DataFrame, lcol: str, icol: str, title: str):
    grid = [[0] * 5 for _ in range(5)]
    for _, r in data.iterrows():
        grid[int(r[lcol]) - 1][int(r[icol]) - 1] += 1
    z = [[score(l, i) for i in range(1, 6)] for l in range(1, 6)]
    text = [[str(grid[l][i]) if grid[l][i] else "" for i in range(5)] for l in range(5)]
    fig = go.Figure(go.Heatmap(
        z=z, x=[f"{i} {IMPACT[i]}" for i in range(1, 6)], y=[f"{l} {LIKELIHOOD[l]}" for l in range(1, 6)],
        text=text, texttemplate="%{text}", textfont={"size": 20, "color": T.BG, "family": "Space Mono"},
        colorscale=T.HEAT_SCALE, opacity=0.92,
        showscale=False, xgap=2, ygap=2,
        hovertemplate="Likelihood %{y}<br>Impact %{x}<br>Score %{z}<extra></extra>"))
    fig.update_layout(title=title, height=380, margin=dict(l=10, r=10, t=50, b=10),
                      xaxis_title="Impact", yaxis_title="Likelihood")
    return fig


# ------------------------------------------------------------------ pages
if page == "Dashboard":
    T.page_title(st, "ISO/IEC 27001:2022 · clause 6.1.2 · risk assessment", "Risk Dashboard",
                 "inherent vs residual risk, every AI call signed off by a human.")
    if df.empty:
        st.info("No risks yet. Use **Assess New Risk** or load the sample data from the sidebar.")
        st.stop()
    pending = int((df.status == AI_FLAG).sum())
    avg_in, avg_res = df.inherent_score.mean(), df.residual_score.mean()
    c = st.columns(5)
    c[0].metric("Risks in register", len(df))
    c[1].metric("Awaiting human validation", pending)
    c[2].metric("Avg inherent risk", f"{avg_in:.1f}")
    c[3].metric("Avg residual risk", f"{avg_res:.1f}", delta=f"{avg_res - avg_in:.1f}", delta_color="inverse")
    c[4].metric("Above appetite (residual > %d)" % RISK_APPETITE, int((df.residual_score > RISK_APPETITE).sum()))
    if pending:
        st.warning(f"{pending} risk(s) are still marked **{AI_FLAG}**.")

    a, b = st.columns(2)
    a.plotly_chart(heatmap(df, "likelihood", "impact", "Inherent risk heat map"), width="stretch")
    b.plotly_chart(heatmap(df, "residual_likelihood", "residual_impact", "Residual risk heat map"),
                   width="stretch")

    long = df.melt(id_vars=["risk_ref", "asset"], value_vars=["inherent_score", "residual_score"],
                   var_name="Stage", value_name="Score")
    long["Stage"] = long["Stage"].map({"inherent_score": "Inherent", "residual_score": "Residual"})
    fig = px.bar(long, x="risk_ref", y="Score", color="Stage", barmode="group", hover_data=["asset"],
                 color_discrete_map={"Inherent": T.CRITICAL, "Residual": T.MINT},
                 title="Inherent vs residual score per risk")
    fig.add_hline(y=RISK_APPETITE, line_dash="dash", line_color=T.CREAM, annotation_text="risk appetite",
                  annotation_font_color=T.CREAM)
    st.plotly_chart(fig, width="stretch")

    a, b = st.columns(2)
    counts = df.residual_rating.value_counts().reindex(["Critical", "High", "Medium", "Low"]).fillna(0)
    a.plotly_chart(px.pie(names=counts.index, values=counts.values, hole=0.5,
                          color=counts.index, color_discrete_map=RATING_COLOURS,
                          title="Residual risk by rating"), width="stretch")
    ctrl = pd.Series([theme_of(c) for cl in df.controls for c in cl]).value_counts()
    b.plotly_chart(px.bar(x=ctrl.index, y=ctrl.values, labels={"x": "Annex A theme", "y": "Control links"},
                          title="Annex A controls applied by theme", color_discrete_sequence=[T.MINT]),
                   width="stretch")

elif page == "Assess New Risk":
    T.page_title(st, "step 01 · identify and analyse", "Assess a New Risk",
                 "describe the exposure; the AI proposes, you decide.")
    with st.form("risk_form"):
        a, b = st.columns(2)
        asset = a.text_input("Asset *", placeholder="e.g. VPN gateway")
        owner = b.text_input("Risk owner", placeholder="e.g. IT Infrastructure Lead")
        threat = a.text_input("Threat *", placeholder="e.g. Credential stuffing")
        vuln = b.text_input("Vulnerability *", placeholder="e.g. Remote access without MFA")
        desc = st.text_area("Context / description")
        go_btn = st.form_submit_button("> get AI suggestion", type="primary")
    if go_btn:
        if not (asset and threat and vuln):
            st.error("Asset, threat and vulnerability are required.")
        else:
            with st.spinner("Asking the AI engine..."):
                st.session_state.sug = suggest(asset, threat, vuln, desc)
                st.session_state.form = dict(asset=asset, threat=threat, vulnerability=vuln,
                                             description=desc, owner=owner)

    if "sug" in st.session_state:
        s = st.session_state.sug
        ai_banner()
        st.caption(f"Source: {s.source}")
        st.write(f"**Rationale:** {s.rationale}")
        a, b, c = st.columns(3)
        L = a.slider("Likelihood", 1, 5, s.likelihood)
        I = a.slider("Impact", 1, 5, s.impact)
        a.metric("Inherent score", f"{L * I} ({rating(L * I)})")
        RL = b.slider("Residual likelihood", 1, 5, s.residual_likelihood)
        RI = b.slider("Residual impact", 1, 5, s.residual_impact)
        b.metric("Residual score", f"{RL * RI} ({rating(RL * RI)})")
        treat = c.selectbox("Treatment", TREATMENTS, index=TREATMENTS.index(s.treatment))
        ctrls = c.multiselect("Annex A controls", list(ANNEX_A), default=s.controls,
                              format_func=lambda x: f"A.{x} {ANNEX_A[x]}")
        plan = st.text_area("Treatment plan", s.treatment_plan)
        if st.button("save to register  [ pending human validation ]"):
            s.likelihood, s.impact, s.residual_likelihood, s.residual_impact = L, I, RL, RI
            s.treatment, s.controls, s.treatment_plan = treat, ctrls, plan
            ref = db.add_risk(conn, suggestion=s, actor=user, **st.session_state.form)
            del st.session_state["sug"]
            st.success(f"Saved as {ref}. Validate it in the Risk Register.")

elif page == "Risk Register":
    T.page_title(st, "step 02 · evaluate and validate", "Risk Register", "review, edit, validate or reject.")
    if df.empty:
        st.info("Register is empty.")
        st.stop()
    f1, f2 = st.columns(2)
    status_f = f1.multiselect("Status", sorted(df.status.unique()), default=sorted(df.status.unique()))
    rating_f = f2.multiselect("Residual rating", ["Critical", "High", "Medium", "Low"],
                              default=["Critical", "High", "Medium", "Low"])
    view = df[df.status.isin(status_f) & df.residual_rating.isin(rating_f)]
    st.dataframe(register_table(view)[["Risk ID", "Asset", "Vulnerability", "Inherent Score",
                                       "Inherent Rating", "Treatment", "Annex A Controls",
                                       "Residual Score", "Residual Rating", "Validation Status",
                                       "Validated By"]], width="stretch", hide_index=True)

    st.subheader("Review a risk")
    ref = st.selectbox("Select risk", df.risk_ref, format_func=lambda r: f"{r} - "
                       f"{df.set_index('risk_ref').loc[r, 'asset']}")
    r = db.get_risk(conn, ref)
    ctrls = json.loads(r["controls"] or "[]")
    if r["status"] == AI_FLAG:
        ai_banner()
    else:
        st.success(f"Status: {r['status']} by {r['validated_by']} at {r['validated_at']}")
    st.write(f"**Threat:** {r['threat']}  \n**Vulnerability:** {r['vulnerability']}  \n"
             f"**Owner:** {r['owner'] or '-'}  \n**Source:** {r['ai_source']}")
    if r["ai_rationale"]:
        st.caption(r["ai_rationale"])

    with st.form(f"edit_{ref}"):
        a, b, c = st.columns(3)
        L = a.slider("Likelihood", 1, 5, r["likelihood"])
        I = a.slider("Impact", 1, 5, r["impact"])
        RL = b.slider("Residual likelihood", 1, 5, r["residual_likelihood"])
        RI = b.slider("Residual impact", 1, 5, r["residual_impact"])
        treat = c.selectbox("Treatment", TREATMENTS, index=TREATMENTS.index(r["treatment"])
                            if r["treatment"] in TREATMENTS else 0)
        owner = c.text_input("Owner", r["owner"] or "")
        new_ctrls = st.multiselect("Annex A controls", list(ANNEX_A), default=ctrls,
                                   format_func=lambda x: f"A.{x} {ANNEX_A[x]}")
        plan = st.text_area("Treatment plan", r["treatment_plan"] or "")
        if st.form_submit_button("Save edits"):
            db.update_risk(conn, ref, user, likelihood=L, impact=I, residual_likelihood=RL,
                           residual_impact=RI, treatment=treat, owner=owner, controls=new_ctrls,
                           treatment_plan=plan)
            st.success("Saved (logged in audit trail).")
            st.rerun()

    st.markdown("**Human validation**")
    comment = st.text_input("Validation comment", key=f"c_{ref}")
    a, b, c = st.columns(3)
    if a.button("validate", type="primary"):
        db.set_status(conn, ref, db.STATUS_VALIDATED, user, comment)
        st.rerun()
    if b.button("reject"):
        db.set_status(conn, ref, db.STATUS_REJECTED, user, comment)
        st.rerun()
    if c.button("delete risk"):
        db.delete_risk(conn, ref, user)
        st.rerun()

elif page == "Annex A Controls":
    T.page_title(st, "93 controls · 4 themes", "Annex A Controls", "coverage of the 2022 control set.")
    soa = soa_table(df)
    c = st.columns(4)
    for i, (k, v) in enumerate(THEMES.items()):
        t = soa[soa.Theme == v]
        c[i].metric(f"{v} ({len(t)})", f"{(t['Linked Risks'] > 0).sum()} in use")
    theme = st.selectbox("Theme", ["All"] + list(THEMES.values()))
    st.dataframe(soa if theme == "All" else soa[soa.Theme == theme], width="stretch",
                 hide_index=True)

elif page == "Export":
    T.page_title(st, "evidence pack", "Audit-ready Export", "register, statement of applicability, audit log.")
    st.write("The Excel workbook contains **Summary**, **Risk Register**, **Statement of "
             "Applicability** (all 93 Annex A controls) and the full **Audit Log**.")
    if df.empty:
        st.info("Nothing to export yet.")
    else:
        st.download_button("download excel workbook (.xlsx)", to_excel(df, db.audit_df(conn)),
                           "GRC_AI_Risk_Register.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("download register (.csv)", to_csv(df), "GRC_AI_Risk_Register.csv", "text/csv")
        st.dataframe(register_table(df), width="stretch", hide_index=True)

elif page == "Audit Log":
    T.page_title(st, "accountability", "Audit Trail", "every suggestion, edit and sign-off.")
    st.caption("Every AI suggestion, edit, validation, rejection and deletion is recorded.")
    st.dataframe(db.audit_df(conn), width="stretch", hide_index=True)

st.sidebar.markdown("---")
st.sidebar.caption("AI output is advisory. Final risk decisions rest with the risk owner.")
st.markdown(T.footer(), unsafe_allow_html=True)
