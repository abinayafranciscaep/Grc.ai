"""AFEP visual identity - shared by every dashboard and report in this portfolio.

Dark-green terminal aesthetic: Space Mono for headings / labels, Space Grotesk for body text,
cream headings, mint accents, thin grid lines and square, outlined controls.
Fonts are bundled in static/fonts (SIL Open Font License) so everything works offline.
"""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "static" / "fonts"

# ------------------------------------------------------------------ palette
BG = "#0C231D"          # page background
PANEL = "#0F2B24"       # cards, tables, chart plot area
PANEL_2 = "#133229"     # hover / header rows
GRID = "#173A31"        # background grid lines
BORDER = "#305148"      # outlines and dividers
CREAM = "#FFFAD0"       # headings, primary buttons
TEXT = "#C9D2B8"        # body text
MUTED = "#7F978A"       # captions
MINT = "#A5D3B7"        # labels, accents
MINT_DIM = "#5E9A7E"

# severity / status colours tuned to the palette
CRITICAL = "#FF7B6B"
HIGH = "#F2A65A"
MEDIUM = "#E8D48B"
LOW = "#7FC8A0"
INFO = "#8AB4D6"
SEVERITY = {"critical": CRITICAL, "high": HIGH, "medium": MEDIUM, "low": LOW, "info": INFO}
SERIES = [MINT, CREAM, HIGH, INFO, CRITICAL, "#C7A8E0", MINT_DIM, MEDIUM, "#9FB8AD"]
HEAT_SCALE = [[0.0, "#5E9A7E"], [0.2, "#8FBF8F"], [0.45, "#E8D48B"], [0.7, "#F2A65A"], [1.0, "#FF7B6B"]]

MONO = "'Space Mono', ui-monospace, Consolas, monospace"
SANS = "'Space Grotesk', 'Segoe UI', system-ui, sans-serif"
BRAND = "·AFEP·"
SITE = "abinayaf.netlify.app"
AUTHOR = "Abinaya Francisca E P"

FONT_FILES = {("Space Mono", 400): "SpaceMono-Regular.woff2", ("Space Mono", 700): "SpaceMono-Bold.woff2",
              ("Space Grotesk", 300): "SpaceGrotesk-Light.woff2", ("Space Grotesk", 400): "SpaceGrotesk-Regular.woff2",
              ("Space Grotesk", 500): "SpaceGrotesk-Medium.woff2", ("Space Grotesk", 700): "SpaceGrotesk-Bold.woff2"}


@lru_cache(maxsize=1)
def font_face_css(embed: bool = True) -> str:
    """@font-face rules. embed=True inlines the fonts (self-contained HTML files)."""
    rules = []
    for (family, weight), fn in FONT_FILES.items():
        p = FONT_DIR / fn
        if embed and p.exists():
            src = "data:font/woff2;base64," + base64.b64encode(p.read_bytes()).decode()
        else:
            src = f"app/static/fonts/{fn}"
        rules.append(f"@font-face{{font-family:'{family}';font-weight:{weight};font-style:normal;"
                     f"font-display:swap;src:url({src}) format('woff2');}}")
    return "\n".join(rules)


BASE_CSS = f"""
:root {{ --bg:{BG}; --panel:{PANEL}; --grid:{GRID}; --border:{BORDER}; --cream:{CREAM};
        --text:{TEXT}; --muted:{MUTED}; --mint:{MINT}; }}
html, body {{ background:{BG}; color:{TEXT}; font-family:{SANS}; }}
body {{ background-image: linear-gradient({GRID} 1px, transparent 1px),
                          linear-gradient(90deg, {GRID} 1px, transparent 1px);
        background-size: 48px 48px; background-attachment: fixed; }}
h1, h2, h3, h4 {{ font-family:{MONO}; color:{CREAM}; font-weight:700; letter-spacing:-0.01em; }}
h1 {{ text-shadow: 3px 3px 0 #2B4A3A; }}
a {{ color:{MINT}; }}
code, pre, .mono {{ font-family:{MONO}; }}
.afep-eyebrow {{ font-family:{MONO}; color:{MINT}; text-transform:uppercase; letter-spacing:0.28em;
                font-size:0.78rem; margin:0 0 .4rem 0; }}
.afep-prompt {{ font-family:{MONO}; color:{CREAM}; opacity:.92; font-size:1.05rem; margin:.2rem 0 1rem 0; }}
.afep-brand {{ font-family:{MONO}; color:{CREAM}; font-weight:700; letter-spacing:.08em; font-size:1.05rem; }}
.afep-tag {{ font-family:{MONO}; border:1px solid {BORDER}; color:{MINT}; padding:4px 10px; font-size:.78rem;
            display:inline-block; }}
.afep-rule {{ border:0; border-top:1px solid {BORDER}; margin:14px 0; }}
.afep-foot {{ font-family:{MONO}; color:{MUTED}; font-size:.72rem; letter-spacing:.12em; }}
"""

# extra rules that restyle Streamlit's own widgets
STREAMLIT_CSS = f"""
[data-testid="stAppViewContainer"], [data-testid="stApp"] {{
    background-color:{BG};
    background-image: linear-gradient({GRID} 1px, transparent 1px), linear-gradient(90deg, {GRID} 1px, transparent 1px);
    background-size:48px 48px; }}
[data-testid="stHeader"] {{ background:transparent; }}
[data-testid="stSidebar"] {{ background:{PANEL}; border-right:1px solid {BORDER}; }}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] input,
[data-testid="stSidebar"] summary p {{ font-family:{MONO}; }}
[data-testid="stIconMaterial"] {{ font-family:'Material Symbols Rounded' !important; }}
h1 {{ font-size:2.4rem !important; text-shadow:3px 3px 0 #2B4A3A; }}
h1, h2, h3, h4 {{ font-family:{MONO} !important; color:{CREAM} !important; }}
[data-testid="stMetric"] {{ border:1px solid {BORDER}; background:{PANEL}cc; padding:12px 14px; }}
[data-testid="stMetricLabel"] p {{ font-family:{MONO}; color:{MINT} !important; text-transform:uppercase;
                                   letter-spacing:.14em; font-size:.72rem !important; }}
[data-testid="stMetricValue"] {{ font-family:{MONO}; color:{CREAM}; }}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {{
    font-family:{MONO}; background:transparent !important; color:{CREAM} !important;
    border:1px solid {CREAM} !important; border-radius:0 !important; letter-spacing:.06em; }}
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover {{
    background:{CREAM} !important; color:{BG} !important; }}
.stButton > button[kind="secondary"] {{ border-color:{BORDER} !important; color:{MINT} !important; }}
[data-testid="stForm"], [data-testid="stExpander"] details {{ border:1px solid {BORDER} !important;
    border-radius:0 !important; background:{PANEL}aa; }}
[data-testid="stAlert"] {{ border-radius:0 !important; font-family:{MONO}; }}
[data-testid="stDataFrame"] {{ border:1px solid {BORDER}; }}
[data-testid="stCaptionContainer"] {{ font-family:{MONO}; color:{MUTED}; }}
hr {{ border-color:{BORDER} !important; }}
"""


def html_head(title: str) -> str:
    """<head> content for stand-alone HTML reports (fonts embedded)."""
    return (f"<meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{title}</title><style>{font_face_css(True)}\n{BASE_CSS}</style>")


def hero(eyebrow: str, title: str, prompt: str) -> str:
    return (f"<p class='afep-eyebrow'>{eyebrow}</p><h1>{title}</h1>"
            f"<p class='afep-prompt'>&gt; {prompt}</p>")


def footer() -> str:
    return (f"<hr class='afep-rule'><p class='afep-foot'>{BRAND} &nbsp; {AUTHOR.upper()} &nbsp;·&nbsp; "
            f"{SITE}</p>")


# ------------------------------------------------------------------ Streamlit
def streamlit_setup(st, eyebrow: str, title: str, prompt: str, show_hero: bool = True):
    # fonts are served from static/fonts via .streamlit/config.toml ([[theme.fontFaces]])
    st.markdown(f"<style>{font_face_css(False)}\n{BASE_CSS}\n{STREAMLIT_CSS}</style>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<div class='afep-brand'>{BRAND}</div>"
                        f"<div class='afep-foot' style='margin-top:4px'>{SITE}</div>"
                        f"<hr class='afep-rule'>", unsafe_allow_html=True)
    register_plotly()
    if show_hero:
        st.markdown(hero(eyebrow, title, prompt), unsafe_allow_html=True)


def page_title(st, eyebrow: str, title: str, prompt: str | None = None):
    st.markdown(hero(eyebrow, title, prompt) if prompt else
                f"<p class='afep-eyebrow'>{eyebrow}</p><h1>{title}</h1>", unsafe_allow_html=True)


# ------------------------------------------------------------------ Plotly
def register_plotly():
    import plotly.graph_objects as go
    import plotly.io as pio
    if "afep" in pio.templates:
        pio.templates.default = "afep"
        return
    t = go.layout.Template()
    t.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=PANEL,
        font=dict(family="Space Mono, Consolas, monospace", color=TEXT, size=12),
        title=dict(font=dict(family="Space Mono, monospace", color=CREAM, size=15), x=0, xanchor="left"),
        colorway=SERIES,
        xaxis=dict(automargin=True, gridcolor=GRID, linecolor=BORDER, zerolinecolor=BORDER, tickcolor=BORDER,
                   title=dict(font=dict(color=MINT))),
        yaxis=dict(automargin=True, gridcolor=GRID, linecolor=BORDER, zerolinecolor=BORDER, tickcolor=BORDER,
                   title=dict(font=dict(color=MINT))),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=BORDER, font=dict(color=TEXT)),
        hoverlabel=dict(bgcolor=PANEL_2, bordercolor=MINT, font=dict(family="Space Mono", color=CREAM)),
        margin=dict(l=60, r=20, t=60, b=50),
    )
    t.data.bar = [go.Bar(marker=dict(line=dict(width=0)))]
    pio.templates["afep"] = t
    pio.templates.default = "afep"


# ------------------------------------------------------------------ Matplotlib
def matplotlib_style():
    import matplotlib as mpl
    from matplotlib import font_manager
    for fn in ("SpaceMono-Regular", "SpaceMono-Bold"):
        ttf = FONT_DIR / f"{fn}.ttf"
        if ttf.exists():
            font_manager.fontManager.addfont(str(ttf))
    mpl.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": PANEL, "savefig.facecolor": BG,
        "axes.edgecolor": BORDER, "axes.labelcolor": MINT, "axes.titlecolor": CREAM,
        "xtick.color": TEXT, "ytick.color": TEXT, "text.color": TEXT, "grid.color": GRID,
        "font.family": "monospace", "font.monospace": ["Space Mono", "DejaVu Sans Mono"],
        "axes.titleweight": "bold", "axes.prop_cycle": mpl.cycler(color=SERIES)})
