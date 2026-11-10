"""Small visual system shared by the planning surfaces."""
from html import escape
import streamlit as st


def theme():
    st.markdown("""<style>
    .stApp {background:#f6f7f3;color:#182e31}
    .block-container {max-width:1120px;padding-top:2.4rem;padding-bottom:4rem}
    h1,h2,h3 {letter-spacing:-.035em;color:#163c3b}
    h1 {font-weight:750;font-size:2.8rem !important;line-height:1.15}
    h2 {font-size:1.6rem !important} h3 {font-size:1.2rem !important}
    [data-testid="stSidebar"] {background:#e9efea;border-right:1px solid #d8e2da}
    [data-testid="stSidebar"] .block-container {padding-top:1rem}
    [data-testid="stMetric"] {background:white;border:1px solid #dce5de;border-radius:16px;padding:1.1rem 1.3rem}
    [data-testid="stMetricValue"] {font-size:1.9rem;color:#163c3b;letter-spacing:-.04em}
    [data-testid="stMetricLabel"] {color:#526462;font-size:.85rem}
    [data-testid="stVerticalBlockBorderWrapper"] > div {border-radius:16px !important}
    [data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button,
    [data-testid="stDownloadButton"] button {min-height:2.8rem;border-radius:10px;font-weight:600}
    button:focus-visible,a:focus-visible {outline:3px solid #bf7725 !important;outline-offset:3px}
    [data-testid="stCaptionContainer"] {color:#536763;line-height:1.5}
    [data-testid="stExpander"] {background:#ffffff88;border-radius:12px}
    .ml-eyebrow {font-size:.73rem;letter-spacing:.17em;font-weight:750;color:#57716b;margin-bottom:.65rem}
    .ml-brand {font-size:1.55rem;letter-spacing:-.05em;font-weight:800;color:#163c3b;padding:1rem 0 .3rem}
    .ml-hero {background:#173f3e;color:#f8faf4;border-radius:22px;padding:2rem;margin:0 0 1.5rem;position:relative;overflow:hidden}
    .ml-hero h2 {color:#f8faf4;font-size:2rem !important;max-width:650px;margin:.35rem 0 .7rem}
    .ml-hero p {color:#d7e6df;max-width:610px;line-height:1.65;margin:0}
    .ml-hero .ml-eyebrow {color:#a9d3b9}
    .ml-status {display:inline-block;padding:.25rem .65rem;background:#e5eee5;color:#28594c;border-radius:30px;font-size:.75rem;font-weight:650;margin-bottom:.5rem}
    .ml-status.attention {background:#fff0d9;color:#805018}
    .ml-goal {padding:.15rem 0 .5rem}.ml-goal-title {font-size:1.05rem;font-weight:700;margin-bottom:.3rem}
    .ml-goal-amount {font-size:1.65rem;font-weight:700;letter-spacing:-.03em;color:#173f3e}
    .ml-goal-small {font-size:.85rem;color:#58706a}
    @media(max-width:768px) {
      .block-container{padding:1.4rem 1rem 3rem} h1{font-size:2rem !important}
      .ml-hero{padding:1.4rem;border-radius:16px}.ml-hero h2{font-size:1.6rem !important}
      [data-testid="stMetric"]{padding:.8rem} [data-testid="stMetricValue"]{font-size:1.5rem}
    }
    @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto !important}}
    </style>""", unsafe_allow_html=True)


def eyebrow(text):
    st.markdown(f'<div class="ml-eyebrow">{escape(text)}</div>', unsafe_allow_html=True)


def hero(title, detail, *, label="MONEY, WITH A DIRECTION"):
    st.markdown(f'<div class="ml-hero"><div class="ml-eyebrow">{escape(label)}</div>'
                f'<h2>{escape(title)}</h2><p>{escape(detail)}</p></div>', unsafe_allow_html=True)


def goal_summary(name, saved, target, *, on_track):
    status = "On pace in this model" if on_track else "Needs a different pace"
    st.markdown(f'<div class="ml-goal"><span class="ml-status {"" if on_track else "attention"}">{status}</span>'
                f'<div class="ml-goal-title">{escape(name)}</div><span class="ml-goal-amount">${saved:,.2f}</span>'
                f'<span class="ml-goal-small"> of ${target:,.2f} saved</span></div>', unsafe_allow_html=True)
