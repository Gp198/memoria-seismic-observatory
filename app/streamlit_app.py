from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.assistant.context import build_assistant_context
from src.assistant.ui import render_assistant_panel
from src.backtesting.replay import (
    run_replay,
    walk_forward_backtest,
    walk_forward_grid,
)
from src.backtesting.validation import (
    summarise_backtest,
    summarise_backtest_grid,
)
from src.features.fingerprints import FINGERPRINT_FEATURES
from src.pipeline import bootstrap_demo
from src.quality.completeness import estimate_magnitude_completeness
from src.quality.deduplication import preferred_events
from src.quality.declustering import (
    declustering_summary,
    declustering_exclusion_summary,
    select_catalogue_mode,
)
from src.quality.magnitude import (
    magnitude_audit_summary,
    magnitude_policy_summary,
    select_magnitude_policy,
)
from src.quality.statistics import moving_block_percentile_interval
from src.reporting.dashboard_data import (
    activity_label,
    assess_activity_state,
    build_event_map_figure,
    density_grid_resolution_km,
    build_source_pipeline_status,
    build_temporal_aggregation,
    calendar_span_years,
    catalogue_consolidation_summary,
    extract_years,
    format_boolean_pt,
    format_date_pt,
    format_number,
    format_percentage,
    prepare_dashboard_events,
    prepare_dashboard_fingerprints,
    safe_fractional_date,
)
from src.reporting.explanations import replay_summary, similarity_summary
from src.similarity.nearest_states import (
    FEATURE_LABELS_PT,
    nearest_states,
)
from src.storage import load_gold_fingerprints, load_silver_events

APP_VERSION = "0.6.2"
CREATOR = "Gonçalo Pedro"

st.set_page_config(
    page_title="MEMÓRIA | Portuguese Seismic Memory Observatory",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
:root {
  --navy-950:#061726; --navy-900:#08243A; --blue-700:#0D5578;
  --blue-500:#1682A3; --cyan-400:#41B8D5; --ice-100:#EFF7FA;
  --paper:#FFFFFF; --ink:#102A3D; --muted:#687E8F;
  --line:rgba(13,85,120,.13); --shadow:0 14px 38px rgba(6,23,38,.08);
}
html, body, [class*="css"] {font-family:Inter,"Segoe UI",Arial,sans-serif;}
.stApp {
  color:var(--ink);
  background:radial-gradient(circle at 92% 2%,rgba(65,184,213,.17),transparent 30rem),
             linear-gradient(180deg,#F8FBFD 0%,#EEF4F7 100%);
}
.block-container {max-width:1580px;padding-top:1.4rem;padding-bottom:1.2rem;}
[data-testid="stSidebar"] {
  background:radial-gradient(circle at 10% 5%,rgba(65,184,213,.15),transparent 14rem),
             linear-gradient(180deg,var(--navy-950),var(--navy-900));
  border-right:1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] * {color:#F4FAFC;}
.mem-brand{display:flex;align-items:center;gap:.75rem;margin:.2rem 0 1rem;}
.mem-brand-mark{
  width:42px;height:42px;border-radius:14px;display:grid;place-items:center;
  font-size:22px;font-weight:700;color:white;
  background:linear-gradient(135deg,#41B8D5,#0D5578);
  box-shadow:0 10px 24px rgba(65,184,213,.25);
}
.mem-brand-title{font-weight:800;font-size:1.05rem;letter-spacing:.04em;}
.mem-brand-sub{font-size:.72rem;opacity:.68;margin-top:.1rem;}
.mem-side-status{
  padding:.75rem .85rem;border:1px solid rgba(255,255,255,.11);
  border-radius:14px;background:rgba(255,255,255,.055);margin:.7rem 0 1.1rem;
}
.mem-status-dot{
  display:inline-block;width:8px;height:8px;border-radius:50%;
  background:#66E0A3;box-shadow:0 0 0 5px rgba(102,224,163,.12);margin-right:.5rem;
}
.mem-hero{
  position:relative;overflow:hidden;padding:1.65rem 1.85rem 1.55rem;
  border-radius:24px;
  background:radial-gradient(circle at 88% 15%,rgba(65,184,213,.30),transparent 19rem),
             linear-gradient(125deg,#061726 0%,#0A3E5E 58%,#137C98 100%);
  box-shadow:0 22px 58px rgba(6,23,38,.18);color:white;margin-bottom:1rem;
}
.mem-hero:after{
  content:"";position:absolute;right:-55px;bottom:-105px;width:290px;height:290px;
  border-radius:50%;border:1px solid rgba(255,255,255,.14);
  box-shadow:0 0 0 36px rgba(255,255,255,.035),0 0 0 72px rgba(255,255,255,.025);
}
.mem-eyebrow{
  font-size:.72rem;font-weight:800;letter-spacing:.15em;text-transform:uppercase;
  color:#9DE8F5;margin-bottom:.55rem;
}
.mem-hero h1{margin:0;font-size:clamp(2rem,4vw,3.15rem);letter-spacing:-.045em;line-height:1;}
.mem-hero p{margin:.7rem 0 0;opacity:.84;max-width:900px;font-size:.98rem;line-height:1.55;}
.mem-hero-meta{display:flex;flex-wrap:wrap;gap:.55rem;margin-top:1.15rem;}
.mem-chip{
  display:inline-flex;align-items:center;gap:.35rem;padding:.34rem .68rem;
  border-radius:999px;background:rgba(255,255,255,.10);
  border:1px solid rgba(255,255,255,.16);font-size:.72rem;font-weight:700;
}
.mem-created{color:#C9F5FB;font-weight:800;}
.mem-section-head{
  display:flex;justify-content:space-between;align-items:flex-end;gap:1rem;margin:1rem 0 .7rem;
}
.mem-section-head h2{margin:0;font-size:1.2rem;letter-spacing:-.02em;}
.mem-section-head p{margin:.18rem 0 0;color:var(--muted);font-size:.83rem;}
.mem-badge{
  display:inline-flex;align-items:center;padding:.35rem .65rem;border-radius:999px;
  font-weight:800;font-size:.72rem;white-space:nowrap;
}
.mem-badge-normal{background:#E4F7ED;color:#17613A;}
.mem-badge-watch{background:#FFF3D7;color:#7A5100;}
.mem-badge-high{background:#FFE4E4;color:#8B2626;}
.mem-badge-neutral{background:#EDF2F5;color:#516778;}
.mem-insight{
  background:linear-gradient(135deg,#FFFFFF,#F3FAFC);border:1px solid var(--line);
  border-radius:18px;padding:1.05rem 1.15rem;box-shadow:var(--shadow);height:100%;
}
.mem-insight-label{
  color:var(--blue-700);font-size:.69rem;font-weight:900;
  letter-spacing:.1em;text-transform:uppercase;
}
.mem-insight h3{margin:.35rem 0 .35rem;font-size:1.05rem;}
.mem-insight p{margin:0;color:var(--muted);font-size:.84rem;line-height:1.48;}
.mem-note{
  background:#FFF9E9;border:1px solid #F0D58D;color:#69500D;
  padding:.8rem .95rem;border-radius:13px;font-size:.84rem;
}
.mem-demo{
  background:#E9F7FB;border:1px solid rgba(65,184,213,.35);
  color:#13516A;padding:.8rem 1rem;border-radius:14px;margin:.5rem 0 1rem;
}
.mem-footer{
  margin-top:1.6rem;padding:1rem 1.1rem;border-radius:16px;
  display:flex;justify-content:space-between;align-items:center;gap:1rem;
  background:#071A2D;color:white;font-size:.75rem;
}
.mem-footer strong{color:#9DE8F5;}
div[data-testid="stMetric"]{
  background:rgba(255,255,255,.95);border:1px solid var(--line);
  padding:.85rem 1rem;border-radius:16px;box-shadow:0 8px 25px rgba(6,23,38,.055);
}
div[data-testid="stMetric"] label{color:var(--muted)!important;font-weight:700!important;}
div[data-testid="stMetricValue"]{color:var(--ink);letter-spacing:-.035em;}
[data-testid="stVerticalBlockBorderWrapper"]{
  background:rgba(255,255,255,.86);border-color:var(--line)!important;
  border-radius:18px!important;box-shadow:0 9px 28px rgba(6,23,38,.055);
}
div[role="radiogroup"]{
  gap:.45rem!important;padding:.28rem;border-radius:14px;
  background:rgba(255,255,255,.72);border:1px solid var(--line);width:max-content;
}
div[role="radiogroup"] label{border-radius:10px;padding:.22rem .55rem;}
div[role="radiogroup"] label:has(input:checked){background:#0D5578;color:white;}

/*
 * Sidebar widgets use light surfaces even when the application sidebar is
 * permanently dark. The previous catch-all sidebar rule made the text white
 * on those white surfaces when Streamlit was using its light theme. These
 * selectors give form controls an explicit, theme-independent contrast while
 * leaving normal sidebar copy and assistant replies white.
 */
[data-testid="stSidebar"] input:not([type="radio"]):not([type="checkbox"]),
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] [contenteditable="true"] {
  color:#102A3D!important;
  -webkit-text-fill-color:#102A3D!important;
  caret-color:#0D5578!important;
  color-scheme:light!important;
}
[data-testid="stSidebar"] input:not([type="radio"]):not([type="checkbox"])::placeholder,
[data-testid="stSidebar"] textarea::placeholder {
  color:#718594!important;
  -webkit-text-fill-color:#718594!important;
  opacity:1!important;
}
[data-testid="stSidebar"] input:disabled,
[data-testid="stSidebar"] textarea:disabled {
  color:#516778!important;
  -webkit-text-fill-color:#516778!important;
  opacity:1!important;
}
[data-testid="stSidebar"] [data-baseweb="input"] > div,
[data-testid="stSidebar"] [data-baseweb="textarea"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background:#FFFFFF!important;
  border-color:rgba(13,85,120,.28)!important;
  color:#102A3D!important;
}
[data-testid="stSidebar"] [data-baseweb="input"] *,
[data-testid="stSidebar"] [data-baseweb="textarea"] *,
[data-testid="stSidebar"] [data-baseweb="select"] * {
  color:#102A3D!important;
  -webkit-text-fill-color:#102A3D!important;
}
[data-testid="stSidebar"] [data-baseweb="input"] > div:focus-within,
[data-testid="stSidebar"] [data-baseweb="textarea"] > div:focus-within,
[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within {
  border-color:#41B8D5!important;
  box-shadow:0 0 0 2px rgba(65,184,213,.20)!important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
[data-testid="stSidebar"] button[kind="secondary"] {
  background:#FFFFFF!important;
  border:1px solid rgba(13,85,120,.25)!important;
  color:#102A3D!important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] *,
[data-testid="stSidebar"] button[kind="secondary"] * {
  color:#102A3D!important;
  -webkit-text-fill-color:#102A3D!important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover,
[data-testid="stSidebar"] button[kind="secondary"]:hover {
  background:#EAF7FB!important;
  border-color:#41B8D5!important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"],
[data-testid="stSidebar"] button[kind="primary"] {
  color:#FFFFFF!important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] *,
[data-testid="stSidebar"] button[kind="primary"] * {
  color:#FFFFFF!important;
  -webkit-text-fill-color:#FFFFFF!important;
}
/* BaseWeb renders select options in a portal outside the sidebar DOM. */
[data-baseweb="popover"] [role="option"],
[data-baseweb="menu"] [role="option"],
[data-baseweb="popover"] li {
  background:#FFFFFF!important;
  color:#102A3D!important;
  -webkit-text-fill-color:#102A3D!important;
}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="menu"] [role="option"]:hover {
  background:#EAF7FB!important;
}
.stAlert{border-radius:14px;}
hr{border-color:rgba(13,85,120,.10);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        events = load_silver_events()
        fingerprints = load_gold_fingerprints()
    except FileNotFoundError:
        events, fingerprints = bootstrap_demo()
    return prepare_dashboard_events(events), prepare_dashboard_fingerprints(fingerprints)


def format_mag(value: float) -> str:
    return "—" if pd.isna(value) else f"{float(value):.1f}"


def format_depth(value: float) -> str:
    return "—" if pd.isna(value) else f"{float(value):.1f} km"


def professional_layout(figure: go.Figure, height: int | None = None) -> go.Figure:
    updates = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Inter, Segoe UI, sans-serif", "color": "#17324A"},
        "margin": {"l": 12, "r": 12, "t": 46, "b": 18},
        "hoverlabel": {"bgcolor": "#071A2D", "font": {"color": "white"}, "bordercolor": "#41B8D5"},
        "legend": {"orientation": "h", "y": -0.18},
    }
    if height:
        updates["height"] = height
    figure.update_layout(**updates)
    figure.update_xaxes(gridcolor="rgba(13,85,120,.08)", zeroline=False)
    figure.update_yaxes(gridcolor="rgba(13,85,120,.08)", zeroline=False)
    return figure


def render_header(is_demo: bool, source_count: int, last_year: int | None) -> None:
    catalogue = "DEMONSTRAÇÃO SINTÉTICA" if is_demo else "CATÁLOGO CONSOLIDADO"
    last_year_text = str(last_year) if last_year else "—"
    st.markdown(
        f"""
        <section class="mem-hero">
          <div class="mem-eyebrow">Seismic intelligence · Portugal</div>
          <h1>MEMÓRIA</h1>
          <p>Portuguese Seismic Memory Observatory — uma plataforma de inteligência
          sísmica explicável que compara o estado atual com a memória histórica,
          mede incerteza e valida hipóteses através de replay temporal.</p>
          <div class="mem-hero-meta">
            <span class="mem-chip">◉ {catalogue}</span>
            <span class="mem-chip">◫ {source_count} fontes integradas</span>
            <span class="mem-chip">⌁ dados até {last_year_text}</span>
            <span class="mem-chip mem-created">Criado por {CREATOR}</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section(title: str, subtitle: str, badge: tuple[str, str] | None = None) -> None:
    badge_html = ""
    if badge:
        label, level = badge
        badge_html = f'<span class="mem-badge mem-badge-{level}">{label}</span>'
    st.markdown(
        f"""
        <div class="mem-section-head">
          <div><h2>{title}</h2><p>{subtitle}</p></div>
          {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


events, fingerprints = load_data()
preferred_all = preferred_events(events)
is_demo = preferred_all["source"].astype(str).eq("DEMO").all()
valid_dates = preferred_all["origin_time_utc"].dropna()
valid_years = extract_years(valid_dates).dropna()
last_year = int(valid_years.max()) if not valid_years.empty else None

with st.sidebar:
    st.markdown(
        f"""
        <div class="mem-brand">
          <div class="mem-brand-mark">M</div>
          <div>
            <div class="mem-brand-title">MEMÓRIA</div>
            <div class="mem-brand-sub">Seismic Memory Observatory</div>
          </div>
        </div>
        <div class="mem-side-status">
          <span class="mem-status-dot"></span><b>Sistema operacional</b><br>
          <span style="opacity:.66;font-size:.72rem">Dados locais processados</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    assistant_slot = st.empty()

    domains = sorted(
        domain
        for domain in preferred_all["tectonic_domain"].dropna().unique()
        if domain and domain != "Fora dos domínios piloto"
    )
    if len(domains) == 1:
        selected_domain = domains[0]
        st.text_input(
            "Domínio piloto",
            value=selected_domain,
            disabled=True,
        )
    else:
        selected_domain = st.selectbox("Domínio tectónico", domains)

    catalogue_label = st.radio(
        "Catálogo analítico",
        ["Completo", "Declusterizado · piloto"],
        help=(
            "O modo declusterizado remove eventos associados a sequências "
            "através de uma regra espaço-temporal transparente. Não é uma "
            "implementação oficial de Gardner–Knopoff ou Reasenberg."
        ),
    )
    catalogue_mode = (
        "declustered"
        if catalogue_label.startswith("Declusterizado")
        else "complete"
    )
    magnitude_policy_label = st.radio(
        "Política de magnitude",
        ["Operacional · auditada", "Validada · apenas regras revistas"],
        help=(
            "A política operacional inclui fallbacks explicitamente sinalizados. "
            "A política validada usa apenas Mw e conversões revistas/aprovadas."
        ),
    )
    magnitude_policy = (
        "validated" if magnitude_policy_label.startswith("Validada") else "operational"
    )
    preferred = select_magnitude_policy(
        select_catalogue_mode(preferred_all, catalogue_mode),
        magnitude_policy,
    )

    selected_window = st.select_slider("Janela analítica", options=[30, 90, 365], value=90)
    min_mag = st.slider("Magnitude mínima no mapa", 0.0, 6.0, 1.5, 0.1)

    st.divider()
    domain_sidebar = preferred[preferred["tectonic_domain"] == selected_domain]
    domain_dates = domain_sidebar["origin_time_utc"].dropna()
    if not domain_dates.empty:
        sidebar_years = extract_years(domain_dates).dropna()
        if not sidebar_years.empty:
            st.caption(
                f"Cobertura: {int(sidebar_years.min())}–"
                f"{int(sidebar_years.max())}"
            )
    st.caption(
        f"Eventos preferenciais no domínio: {len(domain_sidebar):,}"
    )
    st.caption(f"Modo analítico: {catalogue_label}")
    st.caption(f"Magnitude: {magnitude_policy_label}")
    sidebar_mag = magnitude_policy_summary(
        preferred_all[preferred_all["tectonic_domain"] == selected_domain]
    )
    st.caption(
        f"Cobertura validada no domínio: "
        f"{sidebar_mag['validated_fraction_total']:.1%}"
    )
    st.caption(f"Fontes no catálogo: {preferred_all['source'].nunique()}")

    st.divider()
    st.markdown("**Princípio científico**")
    st.caption("Semelhança histórica e atividade relativa não equivalem a previsão determinística.")
    st.divider()
    st.markdown(
        f"<div style='font-size:.72rem;opacity:.72'>Versão {APP_VERSION}<br><b>Criado por {CREATOR}</b></div>",
        unsafe_allow_html=True,
    )

render_header(is_demo, int(preferred_all["source"].nunique()), last_year)

if is_demo:
    st.markdown(
        '<div class="mem-demo"><b>Modo demonstração:</b> os eventos apresentados são sintéticos. '
        "Execute a pipeline de ingestão para usar fontes reais.</div>",
        unsafe_allow_html=True,
    )


if magnitude_policy == "validated" and preferred.empty:
    st.error(
        "A política validada não contém eventos para a seleção atual. "
        "É necessário aprovar relações de conversão ou regressar à política operacional."
    )

page = st.radio(
    "Navegação",
    ["Visão geral", "Memória semelhante", "Replay Portugal", "Qualidade e metodologia"],
    horizontal=True,
    label_visibility="collapsed",
)
assistant_page_details: dict[str, object] = {}

domain_events = preferred[
    preferred["tectonic_domain"] == selected_domain
].copy().sort_values("origin_time_utc")

fingerprint_source = fingerprints.copy()
if "catalogue_mode" in fingerprint_source.columns:
    fingerprint_source = fingerprint_source[
        fingerprint_source["catalogue_mode"].astype(str) == catalogue_mode
    ]
if "magnitude_policy" in fingerprint_source.columns:
    fingerprint_source = fingerprint_source[
        fingerprint_source["magnitude_policy"].astype(str) == magnitude_policy
    ]
domain_fp = fingerprint_source[
    (fingerprint_source["tectonic_domain"] == selected_domain)
    & (fingerprint_source["window_days"] == selected_window)
].copy().sort_values("window_end")

if page == "Visão geral":
    if domain_events.empty or domain_fp.empty:
        st.warning("Sem dados suficientes para este domínio e janela.")
    else:
        latest_fp = domain_fp.iloc[-1]
        latest_time = domain_events["origin_time_utc"].dropna().max()
        period_start = latest_time - pd.Timedelta(days=int(selected_window))
        current_events = domain_events[
            (domain_events["origin_time_utc"] >= period_start)
            & (domain_events["origin_time_utc"] <= latest_time)
        ]

        percentile = latest_fp.get(
            "comparable_percentile_event_rate",
            latest_fp.get("historical_percentile_event_rate"),
        )
        comparison_epoch_label = latest_fp.get(
            "comparison_epoch_label",
            "Período comparável",
        )
        comparison_threshold = latest_fp.get(
            "comparison_magnitude_threshold",
            np.nan,
        )
        comparable_count = latest_fp.get(
            "comparable_event_count",
            latest_fp.get("event_count", 0),
        )
        reference_windows = int(
            latest_fp.get("comparable_reference_windows", 0)
            if pd.notna(
                latest_fp.get("comparable_reference_windows", 0)
            )
            else 0
        )
        effective_reference = float(
            latest_fp.get("comparable_effective_sample_size", np.nan)
        )
        percentile_ci_lower = latest_fp.get(
            "comparable_percentile_ci_lower", np.nan
        )
        percentile_ci_upper = latest_fp.get(
            "comparable_percentile_ci_upper", np.nan
        )
        target_epoch = str(latest_fp.get("comparison_epoch", ""))
        comparable_epoch_fp = domain_fp[
            domain_fp.get(
                "comparison_epoch",
                pd.Series("", index=domain_fp.index),
            ).astype(str)
            == target_epoch
        ].dropna(subset=["window_end"])
        comparable_start = (
            comparable_epoch_fp["window_end"].min()
            if not comparable_epoch_fp.empty
            else pd.NaT
        )
        comparable_end = latest_fp["window_end"]
        comparable_years = (
            max(0, int(pd.to_datetime(comparable_end).year)
                - int(pd.to_datetime(comparable_start).year))
            if pd.notna(comparable_start)
            else 0
        )
        prior_comparable_rates = pd.to_numeric(
            comparable_epoch_fp.loc[
                comparable_epoch_fp["window_end"] < latest_fp["window_end"],
                "comparable_event_rate_per_30d",
            ],
            errors="coerce",
        ).dropna().to_numpy(dtype=float)
        bootstrap_interval = moving_block_percentile_interval(
            prior_comparable_rates,
            float(latest_fp["comparable_event_rate_per_30d"]),
            block_length=int(
                latest_fp.get("comparable_overlap_factor", 1)
                if pd.notna(latest_fp.get("comparable_overlap_factor", 1))
                else 1
            ),
            resamples=800,
            random_seed=42,
        )
        ci_lowers = [
            value
            for value in [
                percentile_ci_lower,
                bootstrap_interval.ci_lower,
            ]
            if value is not None and pd.notna(value)
        ]
        ci_uppers = [
            value
            for value in [
                percentile_ci_upper,
                bootstrap_interval.ci_upper,
            ]
            if value is not None and pd.notna(value)
        ]
        conservative_ci_lower = min(ci_lowers) if ci_lowers else np.nan
        conservative_ci_upper = max(ci_uppers) if ci_uppers else np.nan
        assessment = assess_activity_state(
            percentile,
            conservative_ci_lower,
            conservative_ci_upper,
            effective_reference,
        )
        state_badge = (assessment.label, assessment.level)
        assistant_page_details = {
            "activity_state": assessment.label,
            "interpretation": assessment.interpretation,
            "evidence": assessment.evidence,
            "percentile": percentile,
            "conservative_ci_lower": conservative_ci_lower,
            "conservative_ci_upper": conservative_ci_upper,
            "bootstrap_ci_lower": bootstrap_interval.ci_lower,
            "bootstrap_ci_upper": bootstrap_interval.ci_upper,
            "bootstrap_block_length": bootstrap_interval.block_length,
            "effective_reference_windows": effective_reference,
            "mobile_reference_windows": reference_windows,
            "comparison_epoch": comparison_epoch_label,
            "comparison_threshold": comparison_threshold,
            "comparable_events_current_window": comparable_count,
            "total_events_current_window": latest_fp.get("event_count"),
        }
        render_section(
            "Estado sísmico atual",
            f"{selected_domain} · janela móvel de {selected_window} dias",
            state_badge,
        )

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(
            f"Eventos comparáveis M≥{float(comparison_threshold):.1f}",
            f"{int(comparable_count):,}",
        )
        c2.metric("Magnitude máxima", format_mag(latest_fp["maximum_magnitude"]))
        c3.metric("Profundidade mediana", format_depth(latest_fp["median_depth_km"]))
        c4.metric(
            "Percentil na época comparável",
            "—" if pd.isna(percentile) else f"{float(percentile):.0%}",
        )
        if pd.notna(conservative_ci_lower) and pd.notna(conservative_ci_upper):
            c4.caption(
                f"IC conservador 95%: {float(conservative_ci_lower):.0%}–"
                f"{float(conservative_ci_upper):.0%}"
            )
            c4.caption(
                f"Block bootstrap: {format_percentage(bootstrap_interval.ci_lower)}–"
                f"{format_percentage(bootstrap_interval.ci_upper)} · "
                f"bloco {bootstrap_interval.block_length}"
            )
        c5.metric(
            "Qualidade dos dados",
            "—" if pd.isna(latest_fp["data_quality_score"])
            else f"{float(latest_fp['data_quality_score']):.0%}",
        )

        insight1, insight2, insight3 = st.columns(3)
        label, _ = state_badge
        with insight1:
            st.markdown(
                f"""<div class="mem-insight"><div class="mem-insight-label">Leitura do estado</div>
                <h3>{label}</h3><p>{assessment.interpretation} Época
                {comparison_epoch_label}, limiar M≥{float(comparison_threshold):.1f}.
                Foram usadas {reference_windows} janelas móveis, equivalentes a
                aproximadamente {effective_reference if np.isfinite(effective_reference) else 0:.1f}
                observações independentes. {assessment.evidence}</p></div>""",
                unsafe_allow_html=True,
            )
        with insight2:
            span_years = calendar_span_years(domain_events["origin_time_utc"])
            st.markdown(
                f"""<div class="mem-insight"><div class="mem-insight-label">Arquivo e referência</div>
                <h3>Arquivo: {span_years:,} anos</h3><p>Referência estatística comparável:
                {format_date_pt(comparable_start)}–{format_date_pt(comparable_end)}
                · cerca de {comparable_years} anos. O arquivo total não é usado como
                uma única população homogénea.</p></div>""",
                unsafe_allow_html=True,
            )
        with insight3:
            current_max = pd.to_numeric(current_events["magnitude_comparable"], errors="coerce").max()
            felt_count = int(
                current_events.get("felt", pd.Series(dtype="boolean")).fillna(False).sum()
            )
            st.markdown(
                f"""<div class="mem-insight"><div class="mem-insight-label">Janela selecionada</div>
                <h3>{int(comparable_count)} comparáveis · {int(latest_fp['event_count'])} totais</h3>
                <p>M máxima {format_mag(current_max)} · {felt_count} sentidos.
                Modo: {catalogue_label} · {magnitude_policy_label}. Eventos abaixo
                do limiar da época ficam fora do percentil.</p></div>""",
                unsafe_allow_html=True,
            )

        with st.expander("Sensibilidade ao declustering"):
            comparison_rows = []
            for mode_key, mode_label in [
                ("complete", "Catálogo completo"),
                ("declustered", "Declusterizado · piloto"),
            ]:
                comparison_fp = fingerprints[
                    (fingerprints["tectonic_domain"] == selected_domain)
                    & (fingerprints["window_days"] == selected_window)
                    & (
                        fingerprints.get(
                            "catalogue_mode",
                            pd.Series("complete", index=fingerprints.index),
                        ).astype(str)
                        == mode_key
                    )
                    & (
                        fingerprints.get(
                            "magnitude_policy",
                            pd.Series("operational", index=fingerprints.index),
                        ).astype(str)
                        == magnitude_policy
                    )
                ].sort_values("window_end")
                if comparison_fp.empty:
                    continue
                latest_comparison = comparison_fp.iloc[-1]
                comparison_rows.append(
                    {
                        "Catálogo": mode_label,
                        "Eventos comparáveis": int(
                            latest_comparison.get(
                                "comparable_event_count", 0
                            )
                        ),
                        "Taxa por 30 dias": format_number(
                            latest_comparison.get(
                                "comparable_event_rate_per_30d"
                            ),
                            2,
                        ),
                        "Percentil comparável": format_percentage(
                            latest_comparison.get(
                                "comparable_percentile_event_rate"
                            )
                        ),
                        "M máxima": format_mag(
                            latest_comparison.get("maximum_magnitude")
                        ),
                    }
                )
            st.dataframe(
                pd.DataFrame(comparison_rows),
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "A diferença entre os modos mede a sensibilidade das conclusões "
                "à produtividade de sequências. O declustering é uma camada piloto, "
                "não um catálogo oficial."
            )

        render_section(
            "Distribuição e evolução",
            "Geografia dos epicentros, frequência temporal e distribuição das magnitudes.",
        )

        left, right = st.columns([1.5, 1])
        with left:
            with st.container(border=True):
                mapped_count = int(
                    (
                        pd.to_numeric(
                            domain_events["magnitude_comparable"],
                            errors="coerce",
                        )
                        >= min_mag
                    ).sum()
                )
                map_title, map_control = st.columns([3, 1])
                with map_title:
                    st.markdown(
                        f"#### Eventos M ≥ {min_mag:.1f} — mapa epicentral"
                    )
                map_options = [
                    "Densidade",
                    "Pontos agrupados",
                    "Pontos individuais",
                ]
                default_map_index = 0 if mapped_count > 5000 else 1
                with map_control:
                    map_display_label = st.selectbox(
                        "Representação",
                        map_options,
                        index=default_map_index,
                        key="map_display_mode",
                    )
                map_modes = {
                    "Densidade": "density",
                    "Pontos agrupados": "cluster",
                    "Pontos individuais": "points",
                }
                st.caption(
                    f"Subconjunto filtrado: {mapped_count:,} de "
                    f"{len(domain_events):,} eventos. O mapa não representa "
                    "toda a atividade quando o filtro é elevado."
                )
                if map_display_label == "Densidade":
                    map_data_for_resolution = domain_events[
                        pd.to_numeric(domain_events["magnitude_comparable"], errors="coerce") >= min_mag
                    ].dropna(subset=["latitude", "longitude"])
                    grid_km = density_grid_resolution_km(map_data_for_resolution)
                    st.caption(
                        "A densidade usa grelha espacial, transformação log(1+n) "
                        "e limitação robusta no percentil 99. Resolução aproximada: "
                        f"{grid_km:.1f} km por célula."
                    )
                elif (
                    map_display_label == "Pontos individuais"
                    and mapped_count > 5000
                ):
                    st.caption(
                        "A vista individual renderiza uma amostra visual "
                        "determinística de até 5 000 pontos, preservando os eventos "
                        "de maior magnitude. O catálogo analítico não é reduzido."
                    )
                fig_map = build_event_map_figure(
                    domain_events,
                    min_mag,
                    zoom=None,
                    height=500,
                    display_mode=map_modes[map_display_label],
                )
                st.plotly_chart(fig_map, width="stretch")

        with right:
            with st.container(border=True):
                temporal = build_temporal_aggregation(domain_events)
                fig_time = px.area(
                    temporal.data,
                    x=temporal.x_column,
                    y="events",
                    title=temporal.title,
                    labels={temporal.x_column: temporal.axis_title, "events": "Eventos"},
                )
                fig_time.update_traces(line={"width": 2}, fillcolor="rgba(65,184,213,.18)")
                professional_layout(fig_time, height=235)
                st.plotly_chart(fig_time, width="stretch")
                st.caption(
                    "Este gráfico representa cobertura e capacidade de deteção "
                    "do catálogo; não é uma medida física direta da evolução "
                    "da atividade sísmica."
                )

            with st.container(border=True):
                magnitude_events = domain_events.copy()
                magnitude_events["magnitude_comparable"] = pd.to_numeric(
                    magnitude_events["magnitude_comparable"], errors="coerce"
                ).astype(float)
                magnitude_events = magnitude_events[
                    magnitude_events["magnitude_comparable"].between(-3.0, 10.5, inclusive="both")
                ]
                fig_mag = px.histogram(
                    magnitude_events,
                    x="magnitude_comparable",
                    nbins=28,
                    title="Distribuição de magnitude",
                    labels={"magnitude_comparable": "Magnitude", "count": "Eventos"},
                )
                professional_layout(fig_mag, height=235)
                st.plotly_chart(fig_mag, width="stretch")

        with st.container(border=True):
            st.markdown("#### Evolução do fingerprint sísmico por época")
            st.caption(
                "As linhas são interrompidas nas mudanças de época. Cada "
                "segmento usa o limiar comparável indicado na legenda."
            )
            history_mode = st.radio(
                "Série apresentada",
                ["Taxa comparável", "Taxa bruta do catálogo"],
                horizontal=True,
                key="history_series_mode",
            )
            plot_fp = domain_fp.dropna(subset=["window_end"]).copy()
            value_column = (
                "comparable_event_rate_per_30d"
                if history_mode == "Taxa comparável"
                else "event_rate_per_30d"
            )
            y_title = (
                "Taxa comparável por 30 dias"
                if history_mode == "Taxa comparável"
                else "Taxa bruta por 30 dias"
            )

            history_fig = go.Figure()
            epoch_groups = list(
                plot_fp.sort_values("window_end").groupby(
                    ["comparison_epoch", "comparison_epoch_label"],
                    sort=False,
                )
            )
            magnitude_x: list[object] = []
            magnitude_y: list[object] = []
            for position, ((_, epoch_label), epoch_group) in enumerate(
                epoch_groups
            ):
                epoch_group = epoch_group.sort_values("window_end")
                threshold_value = pd.to_numeric(
                    epoch_group["comparison_magnitude_threshold"],
                    errors="coerce",
                ).median()
                threshold_text = (
                    f"M≥{float(threshold_value):.1f}"
                    if pd.notna(threshold_value)
                    else "limiar indisponível"
                )
                history_fig.add_trace(
                    go.Scatter(
                        x=epoch_group["window_end"],
                        y=epoch_group[value_column],
                        mode="lines",
                        name=f"{epoch_label} · {threshold_text}",
                        line={"width": 2.4},
                        connectgaps=False,
                    )
                )
                magnitude_x.extend(epoch_group["window_end"].tolist())
                magnitude_y.extend(epoch_group["maximum_magnitude"].tolist())
                magnitude_x.append(None)
                magnitude_y.append(None)
                if position > 0:
                    boundary = epoch_group["window_end"].min()
                    history_fig.add_shape(
                        type="line",
                        x0=boundary,
                        x1=boundary,
                        y0=0,
                        y1=1,
                        xref="x",
                        yref="paper",
                        line={"dash": "dot", "width": 1},
                    )
                    history_fig.add_annotation(
                        x=boundary,
                        y=1.03,
                        xref="x",
                        yref="paper",
                        text=epoch_label,
                        showarrow=False,
                        font={"size": 10},
                    )

            history_fig.add_trace(
                go.Scatter(
                    x=magnitude_x,
                    y=magnitude_y,
                    mode="lines",
                    name="Magnitude máxima",
                    yaxis="y2",
                    line={"width": 1.4, "dash": "dot"},
                    opacity=0.55,
                    connectgaps=False,
                )
            )
            history_fig.update_layout(
                yaxis={"title": y_title},
                yaxis2={
                    "title": "Magnitude",
                    "overlaying": "y",
                    "side": "right",
                },
                xaxis={"title": "Fim da janela"},
            )
            professional_layout(history_fig, height=410)
            st.plotly_chart(history_fig, width="stretch")
            st.caption(
                "Os segmentos de épocas diferentes não devem ser interpretados "
                "como uma série homogénea: limiar, rede e capacidade de deteção "
                "mudam entre períodos."
            )

        note_class = "mem-note"
        st.markdown(
            f"""<div class="{note_class}"><b>Interpretação responsável:</b>
            {assessment.interpretation} {assessment.evidence} A classificação
            considera o intervalo de incerteza e não demonstra preparação de uma
            grande rutura nem constitui um alerta.</div>""",
            unsafe_allow_html=True,
        )

elif page == "Memória semelhante":
    render_section(
        "Memória sísmica comparável",
        "Famílias temporais não sobrepostas, escalamento robusto e explicação percentual das diferenças.",
    )

    control_1, control_2, control_3, control_4, control_5 = st.columns(
        [1.2, 0.75, 0.95, 1.05, 1.0]
    )
    metric = control_1.radio(
        "Métrica de distância",
        ["euclidean", "mahalanobis"],
        format_func=lambda value: (
            "Euclidiana robusta"
            if value == "euclidean"
            else "Mahalanobis robusta"
        ),
    )
    k = control_2.slider("Famílias", 3, 10, 5)
    exclusion = control_3.slider(
        "Exclusão do estado atual",
        90,
        1095,
        365,
        30,
        help="Distância mínima entre o alvo atual e o histórico elegível.",
    )
    family_method_label = control_4.selectbox(
        "Construção das famílias",
        ["Adaptativa por mudança de regime", "Janela temporal fixa"],
        help=(
            "O modo adaptativo procura alterações robustas na taxa, magnitude, "
            "energia e dispersão. O modo fixo mantém a regra temporal da versão anterior."
        ),
    )
    family_method = (
        "adaptive"
        if family_method_label.startswith("Adaptativa")
        else "fixed"
    )
    default_diversity = max(selected_window * 8, 365)
    diversity = control_5.slider(
        "Duração máxima da família",
        90,
        1825,
        min(default_diversity, 1825),
        30,
        help=(
            "No modo adaptativo funciona como duração máxima de um regime; "
            "no modo fixo é a largura da janela familiar."
        ),
    )

    try:
        result = nearest_states(
            fingerprint_source,
            selected_domain,
            selected_window,
            k=k,
            exclusion_days=exclusion,
            family_gap_days=diversity,
            family_buffer_days=selected_window,
            metric=metric,
            family_method=family_method,
        )
        st.info(similarity_summary(result))

        best = result.neighbours.iloc[0]
        assistant_page_details = {
            "similarity_method": metric,
            "family_method": family_method,
            "requested_families": k,
            "returned_families": len(result.neighbours),
            "exclusion_days": exclusion,
            "maximum_family_days": diversity,
            "best_family_id": best.get("family_id"),
            "best_representative": best.get("episode_id"),
            "best_similarity": best.get("similarity"),
            "best_data_compatibility": best.get("comparability_score"),
            "best_comparable_event_count": best.get("comparable_event_count"),
            "best_maximum_magnitude": best.get("maximum_magnitude"),
            "features_used": list(result.features),
        }
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Melhor semelhança",
            format_percentage(best["similarity"]),
        )
        c2.metric(
            "Compatibilidade dos dados",
            format_percentage(best["comparability_score"]),
        )
        c3.metric(
            "Famílias temporais",
            len(result.neighbours),
        )
        c4.metric(
            "Variáveis utilizadas",
            len(result.features),
        )

        if float(best["comparability_score"]) < 0.75:
            st.warning(
                "A melhor analogia tem compatibilidade limitada entre qualidade "
                "e completude dos catálogos. Deve ser interpretada com cautela."
            )

        with st.container(border=True):
            st.markdown("#### Famílias temporais selecionadas")
            st.caption(
                f"Método: {family_method_label}. Duração máxima de "
                f"{result.family_gap_days} dias e buffer de "
                f"{result.family_buffer_days} dias. Os intervalos finais "
                "não se sobrepõem."
            )
            show = result.neighbours.copy()
            table = pd.DataFrame(
                {
                    "Rank": show["analogue_rank"].astype(int),
                    "Família": show["family_id"],
                    "Representante": show["episode_id"],
                    "Período representativo": [
                        f"{format_date_pt(start)} – {format_date_pt(end)}"
                        for start, end in zip(
                            show["window_start"],
                            show["window_end"],
                        )
                    ],
                    "Período da família": [
                        f"{format_date_pt(start)} – {format_date_pt(end)}"
                        for start, end in zip(
                            show["family_start"],
                            show["family_end"],
                        )
                    ],
                    "Janelas na família": show["family_window_count"].astype(int),
                    "Semelhança": show["similarity"].map(
                        format_percentage
                    ),
                    "Compatibilidade": show[
                        "comparability_score"
                    ].map(format_percentage),
                    "Eventos comparáveis": show["comparable_event_count"].map(
                        lambda value: int(value)
                        if pd.notna(value)
                        else "—"
                    ),
                    "M máxima": show["maximum_magnitude"].map(
                        lambda value: format_number(value, 1)
                    ),
                    "Profundidade mediana": show[
                        "median_depth_km"
                    ].map(
                        lambda value: format_number(
                            value,
                            1,
                            " km",
                        )
                    ),
                    "Dispersão espacial": show[
                        "spatial_dispersion_km"
                    ].map(
                        lambda value: format_number(
                            value,
                            1,
                            " km",
                        )
                    ),
                    "Qualidade": show["data_quality_score"].map(
                        format_percentage
                    ),
                }
            )
            st.dataframe(
                table,
                width="stretch",
                hide_index=True,
            )

        with st.expander("Diagnóstico da compatibilidade dos dados"):
            diagnostic = pd.DataFrame(
                {
                    "Família": result.neighbours["family_id"],
                    "Qualidade": result.neighbours[
                        "quality_compatibility"
                    ].map(format_percentage),
                    "Completude": result.neighbours[
                        "completeness_compatibility"
                    ].map(format_percentage),
                    "Limiar": result.neighbours[
                        "threshold_compatibility"
                    ].map(format_percentage),
                    "Cobertura": result.neighbours[
                        "coverage_compatibility"
                    ].map(format_percentage),
                    "Perfil de fontes": result.neighbours[
                        "source_profile_compatibility"
                    ].map(format_percentage),
                    "Global": result.neighbours[
                        "comparability_score"
                    ].map(format_percentage),
                }
            )
            st.dataframe(
                diagnostic,
                width="stretch",
                hide_index=True,
            )
            st.caption(
                "A compatibilidade combina qualidade, completude, limiar, "
                "cobertura de campos e composição das fontes."
            )
            target_profile = {
                "IPMA": float(result.target.get("source_share_ipma", 0.0)),
                "ISC": float(result.target.get("source_share_isc", 0.0)),
                "AHEAD": float(result.target.get("source_share_ahead", 0.0)),
                "Outras": float(result.target.get("source_share_other", 0.0)),
            }
            st.caption(
                "Perfil de fontes do estado atual: "
                + " · ".join(f"{name} {share:.1%}" for name, share in target_profile.items())
                + ". A penalização mede a diferença desta composição face a cada família."
            )

        best_episode = best["episode_id"]
        contributions = result.feature_differences[
            result.feature_differences["episode_id"] == best_episode
        ].copy()
        contributions = contributions.sort_values(
            "contribution_pct",
            ascending=True,
        )
        top_feature = contributions.iloc[-1]
        assistant_page_details.update(
            {
                "principal_difference_feature": top_feature.get("feature_label"),
                "principal_difference_contribution": top_feature.get("contribution_pct"),
                "feature_contributions": [
                    {
                        "feature": row.get("feature_label"),
                        "contribution_pct": row.get("contribution_pct"),
                    }
                    for _, row in contributions.sort_values(
                        "contribution_pct", ascending=False
                    ).head(6).iterrows()
                ],
            }
        )

        with st.container(border=True):
            st.markdown("#### O que diferencia a melhor analogia")
            st.caption(
                "A contribuição é normalizada para 100% e mostra quais "
                "variáveis mais influenciaram a distância robusta."
            )
            fig_contribution = px.bar(
                contributions,
                x="contribution_pct",
                y="feature_label",
                orientation="h",
                text="contribution_pct",
                title="Contribuição percentual para a diferença",
                labels={
                    "contribution_pct": "Contribuição (%)",
                    "feature_label": "",
                },
            )
            fig_contribution.update_traces(
                texttemplate="%{text:.1f}%",
                textposition="outside",
                cliponaxis=False,
            )
            fig_contribution.update_xaxes(range=[0, 100])
            professional_layout(fig_contribution, height=430)
            st.plotly_chart(fig_contribution, width="stretch")

        st.markdown(
            f"""<div class="mem-note"><b>Principal fator de diferença:</b>
            {top_feature['feature_label']} representa
            {float(top_feature['contribution_pct']):.1f}% da distância explicativa.
            A percentagem não representa causalidade nem capacidade de previsão.</div>""",
            unsafe_allow_html=True,
        )

    except (ValueError, IndexError, np.linalg.LinAlgError) as error:
        st.warning(f"Comparação histórica indisponível: {error}")

elif page == "Replay Portugal":
    render_section(
        "Replay Portugal",
        "Simulação retrospetiva usando apenas a informação conhecida até à data selecionada.",
    )
    available_dates = domain_fp["window_end"].dropna().sort_values()
    if available_dates.empty:
        st.warning("Sem datas elegíveis para replay.")
    else:
        min_timestamp = safe_fractional_date(available_dates, 0.45)
        max_timestamp = available_dates.iloc[-1] - pd.Timedelta(days=90)
        min_date = min_timestamp.date()
        max_date = max_timestamp.date()
        default_candidate = pd.Timestamp("2020-01-01", tz="UTC").date()
        default_date = max(min_date, min(max_date, default_candidate))

        controls = st.columns(4)
        replay_date = controls[0].date_input(
            "Data de corte", value=default_date, min_value=min_date, max_value=max_date
        )
        threshold = controls[1].number_input("Magnitude-alvo", 2.5, 6.0, 4.0, 0.1)
        horizon = controls[2].selectbox("Horizonte futuro", [7, 30, 90, 365], index=1)
        replay_k = controls[3].slider("Famílias análogas", 3, 10, 5)

        try:
            replay = run_replay(
                preferred, fingerprint_source, replay_date, selected_domain,
                selected_window,
                threshold,
                horizon,
                replay_k,
                family_gap_days=max(selected_window * 8, 365),
                family_buffer_days=selected_window,
                family_method="adaptive",
                catalogue_mode=catalogue_mode,
                magnitude_policy=magnitude_policy,
            )
            st.info(replay_summary(replay))
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Frequência ponderada nas famílias", f"{replay.analogue_probability:.1%}")
            c2.metric("Frequência empírica", f"{replay.historical_rate_probability:.1%}")
            c3.metric("Linha de base Poisson", f"{replay.poisson_probability:.1%}")
            c4.metric("Resultado observado", "Ocorreu" if replay.observed_outcome else "Não ocorreu")
            assistant_page_details = {
                "cutoff_date": replay.cutoff,
                "target_magnitude": threshold,
                "future_horizon_days": horizon,
                "requested_analogue_families": replay_k,
                "analogue_weighted_frequency": replay.analogue_probability,
                "empirical_frequency": replay.historical_rate_probability,
                "poisson_baseline": replay.poisson_probability,
                "observed_outcome": replay.observed_outcome,
                "brier_analogue": replay.brier_analogue,
                "brier_empirical": replay.brier_historical,
                "brier_poisson": replay.brier_poisson,
                "training_epoch": replay.baseline.epoch_label,
                "training_start": replay.baseline.training_start,
                "training_end": replay.baseline.training_end,
                "threshold_event_count": replay.baseline.threshold_event_count,
                "exposure_days": replay.baseline.exposure_days,
                "empirical_windows": replay.baseline.empirical_window_count,
                "positive_windows": replay.baseline.empirical_positive_windows,
            }
            st.caption(
                "A frequência das famílias é um score empírico não calibrado. "
                "Só deve ser chamada probabilidade após validação walk-forward "
                "e calibração exclusivamente com cortes anteriores."
            )
            replay_mag_summary = magnitude_policy_summary(
                preferred_all[
                    preferred_all["tectonic_domain"] == selected_domain
                ]
            )
            if (
                magnitude_policy == "operational"
                and replay_mag_summary["fallback_events"] > 0
            ):
                st.warning(
                    f"Política operacional: {replay_mag_summary['fallback_events']:,} "
                    "eventos do domínio usam escala não validada ou fallback. "
                    "O limiar e as estimativas de energia representam análise de "
                    "sensibilidade, não um catálogo Mw homogéneo."
                )
            elif magnitude_policy == "validated":
                st.info(
                    f"Política validada: {replay_mag_summary['validated_events']:,} de "
                    f"{replay_mag_summary['preferred_events']:,} eventos do domínio "
                    "são elegíveis."
                )

            probabilities = pd.DataFrame(
                {
                    "Modelo": ["Famílias · score bruto", "Empírico", "Poisson"],
                    "Estimativa": [
                        replay.analogue_probability,
                        replay.historical_rate_probability,
                        replay.poisson_probability,
                    ],
                    "Brier": [
                        replay.brier_analogue,
                        replay.brier_historical,
                        replay.brier_poisson,
                    ],
                }
            )
            left, right = st.columns(2)
            with left:
                with st.container(border=True):
                    fig_probability = px.bar(
                        probabilities, x="Modelo", y="Estimativa",
                        range_y=[0, 1], title="Estimativas para o horizonte",
                    )
                    professional_layout(fig_probability, height=330)
                    st.plotly_chart(fig_probability, width="stretch")
            with right:
                with st.container(border=True):
                    fig_brier = px.bar(
                        probabilities, x="Modelo", y="Brier",
                        title="Erro de Brier · menor é melhor",
                    )
                    professional_layout(fig_brier, height=330)
                    st.plotly_chart(fig_brier, width="stretch")

            with st.container(border=True):
                st.markdown("#### Famílias utilizadas no replay")
                replay_table = replay.neighbour_outcomes.copy()
                replay_table = pd.DataFrame(
                    {
                        "Família": replay_table["family_id"],
                        "Período da família": [
                            f"{format_date_pt(start)} – {format_date_pt(end)}"
                            for start, end in zip(
                                replay_table["family_start"],
                                replay_table["family_end"],
                            )
                        ],
                        "Representante": replay_table["episode_id"],
                        "Período representativo": [
                            f"{format_date_pt(start)} – {format_date_pt(end)}"
                            for start, end in zip(
                                replay_table["window_start"],
                                replay_table["window_end"],
                            )
                        ],
                        "Semelhança": replay_table["similarity"].map(
                            format_percentage
                        ),
                        "Compatibilidade": replay_table[
                            "comparability_score"
                        ].map(format_percentage),
                        f"Evento M≥{threshold:.1f} nos {horizon} dias seguintes": replay_table[
                            "future_event"
                        ].map(format_boolean_pt),
                    }
                )
                st.dataframe(
                    replay_table,
                    width="stretch",
                    hide_index=True,
                )

            with st.expander("Diagnóstico das linhas de base"):
                baseline = replay.baseline
                b1, b2, b3, b4 = st.columns(4)
                b1.metric(
                    "Época de treino",
                    f"{baseline.training_start.year}–"
                    f"{baseline.training_end.year}",
                )
                b1.caption(baseline.epoch_label)
                b2.metric(
                    "Eventos no limiar",
                    baseline.threshold_event_count,
                )
                b3.metric(
                    "Exposição",
                    f"{baseline.exposure_days / 365.25:.1f} anos",
                )
                b4.metric(
                    "λ Poisson diário",
                    f"{baseline.poisson_lambda_per_day:.6f}",
                )
                st.markdown(
                    f"""
                    - Período: **{format_date_pt(baseline.training_start)}**
                      a **{format_date_pt(baseline.training_end)}**
                    - Janelas empíricas completas: **{baseline.empirical_window_count}**
                    - Janelas positivas: **{baseline.empirical_positive_windows}**
                    - Limiar comum: **M≥{threshold:.1f}**
                    - Horizonte comum: **{horizon} dias**

                    A frequência empírica e o Poisson usam a mesma época,
                    exposição, domínio, limiar e data de corte.
                    """
                )

            with st.expander("Executar backtesting walk-forward"):
                if st.button("Executar série histórica", type="primary"):
                    with st.spinner("A testar cortes históricos..."):
                        scores = walk_forward_backtest(
                            preferred, fingerprint_source, selected_domain,
                            selected_window, threshold, horizon,
                            family_method="adaptive",
                            catalogue_mode=catalogue_mode,
                            magnitude_policy=magnitude_policy,
                        )
                    if scores.empty:
                        st.warning("Histórico insuficiente.")
                    else:
                        validation = summarise_backtest(scores)
                        v1, v2, v3, v4, v5 = st.columns(5)
                        v1.metric("Cortes walk-forward", validation.sample_count)
                        v2.metric("Eventos observados", validation.positive_count)
                        v3.metric(
                            "Taxa observada",
                            f"{validation.positive_count / max(validation.sample_count, 1):.1%}",
                        )
                        v4.metric("Cortes calibrados", validation.calibrated_count)
                        v5.metric(
                            "Positivos calibrados",
                            validation.calibrated_positive_count,
                        )

                        metrics_display = validation.metrics.copy()
                        for column in [
                            "Probabilidade média",
                            "Frequência observada",
                            "BSS vs. empírico",
                            "BSS vs. Poisson",
                            "Erro de calibração esperado",
                            "Average precision",
                        ]:
                            if column in metrics_display:
                                metrics_display[column] = metrics_display[column].map(
                                    format_percentage
                                )
                        if "Brier médio" in metrics_display:
                            metrics_display["Brier médio"] = metrics_display[
                                "Brier médio"
                            ].map(lambda value: format_number(value, 4))
                        st.markdown("#### Desempenho walk-forward")
                        st.dataframe(
                            metrics_display,
                            width="stretch",
                            hide_index=True,
                        )

                        if validation.calibration_status == "adequate":
                            st.success(validation.calibration_message)
                        elif validation.calibration_status == "experimental":
                            st.warning(validation.calibration_message)
                        else:
                            st.warning(validation.calibration_message)
                        st.caption(
                            "A calibração isotónica usa apenas cortes anteriores a cada previsão, "
                            "evitando fuga temporal."
                        )

                        if not validation.calibration.empty:
                            calibration_fig = px.line(
                                validation.calibration,
                                x="Probabilidade média",
                                y="Frequência observada",
                                color="Modelo",
                                markers=True,
                                error_y=(
                                    validation.calibration["IC 95% superior"]
                                    - validation.calibration["Frequência observada"]
                                ),
                                error_y_minus=(
                                    validation.calibration["Frequência observada"]
                                    - validation.calibration["IC 95% inferior"]
                                ),
                                hover_data=["Cortes", "Eventos observados", "Intervalo"],
                                title="Curva de calibração temporal · IC Wilson 95%",
                            )
                            calibration_fig.add_trace(
                                go.Scatter(
                                    x=[0, 1],
                                    y=[0, 1],
                                    mode="lines",
                                    name="Calibração perfeita",
                                    line={"dash": "dash"},
                                )
                            )
                            calibration_fig.update_xaxes(range=[0, 1])
                            calibration_fig.update_yaxes(range=[0, 1])
                            professional_layout(calibration_fig, height=390)
                            st.plotly_chart(
                                calibration_fig,
                                width="stretch",
                            )

                        if not validation.classification.empty:
                            classification_display = validation.classification.copy()
                            for column in [
                                "Limiar de decisão",
                                "Precisão",
                                "Recall",
                                "F1",
                                "Taxa de falsos alarmes",
                            ]:
                                classification_display[column] = (
                                    classification_display[column].map(
                                        format_percentage
                                    )
                                )
                            st.markdown(
                                "#### Falsos alarmes e deteção · limiares para eventos raros"
                            )
                            st.caption(
                                "Os limiares de 0,5% a 10% são compatíveis com prevalências raras; "
                                "50% ocultaria praticamente toda a capacidade de deteção."
                            )
                            st.dataframe(
                                classification_display,
                                width="stretch",
                                hide_index=True,
                            )

                        if not validation.precision_recall.empty:
                            pr_fig = px.line(
                                validation.precision_recall,
                                x="Recall",
                                y="Precisão",
                                color="Modelo",
                                markers=True,
                                hover_data=["Limiar", "Average precision", "Cortes", "Eventos observados"],
                                title="Precision–Recall · avaliação de eventos raros",
                            )
                            pr_fig.update_xaxes(range=[0, 1])
                            pr_fig.update_yaxes(range=[0, 1])
                            professional_layout(pr_fig, height=390)
                            st.plotly_chart(pr_fig, width="stretch")

                        with st.expander("Ver cortes históricos completos"):
                            st.dataframe(
                                validation.scores,
                                width="stretch",
                                hide_index=True,
                            )

                st.divider()
                st.markdown("#### Matriz de validação por magnitude e horizonte")
                grid_1, grid_2, grid_3 = st.columns(3)
                validation_thresholds = grid_1.multiselect(
                    "Magnitudes-alvo",
                    [3.5, 4.0, 4.5, 5.0],
                    default=[3.5, 4.0, 4.5],
                )
                validation_horizons = grid_2.multiselect(
                    "Horizontes (dias)",
                    [7, 30, 90],
                    default=[7, 30, 90],
                )
                validation_frequency = grid_3.selectbox(
                    "Passo entre cortes",
                    ["30D", "60D", "90D"],
                    index=1,
                    format_func=lambda value: {
                        "30D": "30 dias · mais cortes",
                        "60D": "60 dias · equilibrado",
                        "90D": "90 dias · mais rápido",
                    }[value],
                )
                estimated_scenarios = (
                    len(validation_thresholds) * len(validation_horizons)
                )
                st.caption(
                    f"Serão testados {estimated_scenarios} cenários. Cada corte "
                    "usa apenas informação anterior à respetiva data."
                )
                if st.button(
                    "Executar matriz M × horizonte",
                    disabled=estimated_scenarios == 0,
                ):
                    with st.spinner(
                        "A executar validação temporal multiescenário..."
                    ):
                        grid_scores = walk_forward_grid(
                            preferred,
                            fingerprint_source,
                            selected_domain,
                            window_days=selected_window,
                            thresholds=tuple(validation_thresholds),
                            horizons=tuple(validation_horizons),
                            frequency=validation_frequency,
                            family_method="adaptive",
                            catalogue_mode=catalogue_mode,
                            magnitude_policy=magnitude_policy,
                        )
                    if grid_scores.empty:
                        st.warning(
                            "A matriz não produziu cortes históricos suficientes."
                        )
                    else:
                        grid_summary = summarise_backtest_grid(grid_scores)
                        grid_display = grid_summary.copy()
                        for column in [
                            "Probabilidade média",
                            "Frequência observada",
                            "BSS vs. empírico",
                            "BSS vs. Poisson",
                            "Erro de calibração esperado",
                            "Average precision",
                        ]:
                            if column in grid_display.columns:
                                grid_display[column] = grid_display[column].map(
                                    format_percentage
                                )
                        if "Brier médio" in grid_display.columns:
                            grid_display["Brier médio"] = grid_display[
                                "Brier médio"
                            ].map(lambda value: format_number(value, 4))
                        st.dataframe(
                            grid_display,
                            width="stretch",
                            hide_index=True,
                        )

                        family_rows = grid_summary[
                            grid_summary["Modelo"].eq(
                                "Famílias — score bruto"
                            )
                        ].copy()
                        if not family_rows.empty:
                            heatmap_data = family_rows.pivot_table(
                                index="threshold_magnitude",
                                columns="horizon_days",
                                values="BSS vs. Poisson",
                                aggfunc="mean",
                            )
                            heatmap = px.imshow(
                                heatmap_data,
                                text_auto=".2f",
                                aspect="auto",
                                color_continuous_midpoint=0.0,
                                labels={
                                    "x": "Horizonte (dias)",
                                    "y": "Magnitude-alvo",
                                    "color": "BSS vs. Poisson",
                                },
                                title=(
                                    "Brier Skill Score das famílias "
                                    "face ao Poisson"
                                ),
                            )
                            professional_layout(heatmap, height=360)
                            st.plotly_chart(heatmap, width="stretch")
                            st.caption(
                                "Valores positivos superam o Poisson; valores "
                                "negativos indicam desempenho inferior."
                            )
        except (ValueError, OverflowError, pd.errors.OutOfBoundsDatetime) as error:
            st.warning(f"Replay indisponível: {error}")


else:
    render_section(
        "Qualidade, cobertura e metodologia",
        "Consolidação do catálogo, estado das fontes, completude e limites científicos.",
    )

    consolidation = catalogue_consolidation_summary(events)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(
        "Catálogo consolidado · registos brutos",
        f"{consolidation['raw_records']:,}",
    )
    c2.metric(
        "Catálogo consolidado · eventos",
        f"{consolidation['consolidated_events']:,}",
    )
    c3.metric(
        "Catálogo consolidado · redundantes",
        f"{consolidation['redundant_records']:,}",
    )
    c4.metric(
        "Grupos de duplicação",
        f"{consolidation['duplicate_groups']:,}",
    )
    c5.metric(
        "Taxa de consolidação",
        f"{consolidation['consolidation_rate']:.1%}",
    )

    declustering = declustering_summary(events)
    with st.container(border=True):
        st.markdown("#### Sensibilidade a sequências sísmicas")
        d1, d2, d3, d4, d5, d6 = st.columns(6)
        d1.metric("Eventos preferenciais", f"{declustering['preferred_events']:,}")
        d2.metric("Elegíveis", f"{declustering['eligible_events']:,}")
        d3.metric("Fundo + mainshocks", f"{declustering['background_events']:,}")
        d4.metric("Associados", f"{declustering['associated_events']:,}")
        d5.metric("Não elegíveis", f"{declustering['ineligible_events']:,}")
        d6.metric("Gap de reconciliação", f"{declustering['reconciliation_gap']:,}")
        reconciliation = pd.DataFrame({
            "Estado": ["Fundo + mainshocks", "Associados a sequência", "Não elegíveis", "Não classificados"],
            "Registos": [declustering["background_events"], declustering["associated_events"], declustering["ineligible_events"], declustering["unclassified_events"]],
        })
        st.dataframe(reconciliation, width="stretch", hide_index=True)
        exclusions = declustering_exclusion_summary(events)
        if not exclusions.empty:
            with st.expander("Motivos de não elegibilidade"):
                st.dataframe(exclusions, width="stretch", hide_index=True)
        if declustering["reconciliation_gap"] == 0:
            st.success("Reconciliação fechada: todos os eventos preferenciais têm um estado explícito.")
        else:
            st.error(f"Reconciliação incompleta: gap de {declustering['reconciliation_gap']:,} eventos.")
        st.caption(
            "Método piloto espaço-temporal adaptativo. Serve para análise de "
            "sensibilidade entre catálogo completo e declusterizado; não é uma "
            "implementação oficial de Gardner–Knopoff, Reasenberg ou ETAS."
        )

    with st.container(border=True):
        st.markdown("#### Estado das pipelines e fontes")
        source_status = build_source_pipeline_status(events)
        st.dataframe(
            source_status,
            width="stretch",
            hide_index=True,
        )

        pending_sources = source_status[
            source_status["Estado"] != "Integrada"
        ]
        if not pending_sources.empty:
            pending_names = ", ".join(
                pending_sources["Fonte"].astype(str)
            )
            st.warning(
                f"Fontes que exigem atenção: {pending_names}. "
                "Consulte a coluna «Próxima ação»."
            )
        else:
            st.success(
                "Todas as fontes públicas configuradas estão integradas "
                "no catálogo consolidado."
            )

    source_table = (
        preferred.groupby("source")
        .agg(
            events=("event_id_memoria", "count"),
            first_event=("origin_time_utc", "min"),
            last_event=("origin_time_utc", "max"),
            quality=("quality_score", "mean"),
        )
        .reset_index()
    )
    source_table = pd.DataFrame(
        {
            "Fonte": source_table["source"],
            "Eventos consolidados": source_table["events"].astype(int),
            "Primeiro evento": source_table["first_event"].map(
                format_date_pt
            ),
            "Último evento": source_table["last_event"].map(
                format_date_pt
            ),
            "Qualidade média": source_table["quality"].map(
                format_percentage
            ),
        }
    )

    with st.container(border=True):
        st.markdown("#### Cobertura da seleção analítica por fonte")
        st.dataframe(
            source_table,
            width="stretch",
            hide_index=True,
        )

    with st.container(border=True):
        st.markdown("#### Épocas de comparação e limiares")
        epoch_data = fingerprint_source[
            fingerprint_source["tectonic_domain"] == selected_domain
        ].copy()
        epoch_table = (
            epoch_data.sort_values("window_end")
            .groupby(
                [
                    "comparison_epoch",
                    "comparison_epoch_label",
                    "comparison_magnitude_threshold",
                ],
                as_index=False,
            )
            .agg(
                Primeiro=("window_end", "min"),
                Último=("window_end", "max"),
                Janelas=("window_end", "count"),
                Mc_mediana=("catalogue_completeness_mc", "median"),
            )
        )
        epoch_table = pd.DataFrame(
            {
                "Época": epoch_table["comparison_epoch_label"],
                "Limiar comparável": epoch_table[
                    "comparison_magnitude_threshold"
                ].map(lambda value: f"M≥{float(value):.1f}"),
                "Primeira janela": epoch_table["Primeiro"].map(format_date_pt),
                "Última janela": epoch_table["Último"].map(format_date_pt),
                "Janelas": epoch_table["Janelas"].astype(int),
                "Mc mediana": epoch_table["Mc_mediana"].map(
                    lambda value: format_number(value, 1)
                ),
            }
        )
        st.dataframe(
            epoch_table,
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "O percentil é calculado apenas dentro da mesma época e "
            "sobre eventos acima do limiar comparável."
        )

    with st.container(border=True):
        st.markdown("#### Homogeneização e proveniência das magnitudes")
        magnitude_domain = preferred_all[
            preferred_all["tectonic_domain"] == selected_domain
        ]
        magnitude_summary = magnitude_policy_summary(magnitude_domain)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Eventos do domínio", f"{magnitude_summary['preferred_events']:,}")
        m2.metric("Magnitude disponível", f"{magnitude_summary['events_with_magnitude']:,}")
        m3.metric("Política validada", f"{magnitude_summary['validated_events']:,}")
        m4.metric("Cobertura validada", f"{magnitude_summary['validated_fraction_total']:.1%}")
        magnitude_audit = magnitude_audit_summary(magnitude_domain)
        magnitude_display = pd.DataFrame(
            {
                "Escala original": magnitude_audit[
                    "magnitude_original_type"
                ],
                "Estado": magnitude_audit[
                    "magnitude_homogenization_status"
                ],
                "Método": magnitude_audit[
                    "magnitude_homogenization_method"
                ],
                "Registos": magnitude_audit["Registos"],
                "Incerteza mediana": magnitude_audit[
                    "Incerteza_mediana"
                ].map(lambda value: format_number(value, 2)),
                "Primeiro evento": magnitude_audit[
                    "Primeira_data"
                ].map(format_date_pt),
                "Último evento": magnitude_audit[
                    "Última_data"
                ].map(format_date_pt),
            }
        )
        st.dataframe(
            magnitude_display,
            width="stretch",
            hide_index=True,
        )
        review_count = int(
            magnitude_audit.loc[
                magnitude_audit[
                    "magnitude_homogenization_status"
                ].isin(["review_required", "unknown_scale"]),
                "Registos",
            ].sum()
        )
        if review_count:
            st.warning(
                f"{review_count:,} registos usam identidade operacional não "
                "validada ou escala desconhecida. As relações de conversão "
                "devem ser aprovadas por um sismólogo antes de publicação."
            )
        else:
            st.success(
                "Todos os registos possuem regra de homogeneização revista."
            )
        st.caption(
            "Valor original, tipo original, equação, método, estado e incerteza "
            "são preservados no catálogo Silver."
        )

    assistant_page_details = {
        "catalogue_consolidation": catalogue_consolidation_summary(events),
        "declustering": declustering_summary(preferred_all),
        "declustering_exclusions": declustering_exclusion_summary(preferred_all),
        "magnitude_policy_summary": magnitude_policy_summary(
            preferred_all[preferred_all["tectonic_domain"] == selected_domain]
        ),
        "current_selection_event_count": len(domain_events),
    }

    completeness = estimate_magnitude_completeness(
        domain_events["magnitude_comparable"]
    )
    quality_left, quality_right = st.columns(2)
    with quality_left:
        with st.container(border=True):
            st.markdown("#### Magnitude de completude")
            if completeness.sufficient_data:
                st.success(
                    f"Mc ≈ {completeness.mc:.1f}, estimada por máxima "
                    f"curvatura com {completeness.event_count} eventos."
                )
            else:
                st.warning(
                    f"Amostra insuficiente para uma estimativa robusta: "
                    f"{completeness.event_count} eventos válidos."
                )
    with quality_right:
        with st.container(border=True):
            st.markdown("#### Integridade temporal")
            span = calendar_span_years(
                domain_events["origin_time_utc"]
            )
            st.metric("Amplitude do domínio", f"{span:,} anos")
            st.caption(
                "A amplitude histórica não significa uniformidade de "
                "deteção ou qualidade ao longo do tempo."
            )

    st.markdown(
        """<div class="mem-note"><b>Limite científico:</b> o MEMÓRIA identifica
        semelhança, anomalias relativas e desempenho retrospetivo. Não prevê
        com certeza a data, o local ou a magnitude de um sismo e não substitui
        informação oficial do IPMA ou da Proteção Civil.</div>""",
        unsafe_allow_html=True,
    )
    with st.expander("Variáveis do fingerprint"):
        st.code("\n".join(FINGERPRINT_FEATURES))
    with st.expander("Controlos contra fuga temporal"):
        st.markdown(
            """
            - O fingerprint-alvo termina na data de corte.
            - A normalização é ajustada apenas no histórico elegível.
            - Janelas próximas são agrupadas em famílias não sobrepostas.
            - O futuro do alvo é usado apenas para avaliação.
            - O resultado fica comparável com linhas de base.
            """
        )
    with st.expander("Fontes e proveniência"):
        st.markdown(
            """
            - **IPMA:** eventos sísmicos recentes.
            - **ISC:** catálogo instrumental FDSN.
            - **AHEAD/EPICA:** catálogo europeu pré-instrumental.
            - **DEMO:** apenas para demonstração local.
            """
        )

assistant_context = build_assistant_context(
    page=page,
    selected_domain=selected_domain,
    catalogue_label=catalogue_label,
    catalogue_mode=catalogue_mode,
    magnitude_policy_label=magnitude_policy_label,
    magnitude_policy=magnitude_policy,
    selected_window=selected_window,
    minimum_map_magnitude=min_mag,
    domain_events=domain_events,
    domain_fingerprints=domain_fp,
    validated_coverage=sidebar_mag.get("validated_fraction_total"),
    page_details=assistant_page_details,
    app_version=APP_VERSION,
)
with assistant_slot.container():
    render_assistant_panel(context=assistant_context)

st.markdown(
    f"""<footer class="mem-footer">
      <span>MEMÓRIA v{APP_VERSION} · Observatório experimental de inteligência sísmica</span>
      <span><strong>Criado por {CREATOR}</strong> · Portugal</span>
    </footer>""",
    unsafe_allow_html=True,
)
