"""MoneyLab — understand your money, enjoy your life.

Native Streamlit navigation keeps the five main experiences focused. Actual
calculations, financial blocks and state are provided by moneylab.ui_app.
"""

import streamlit as st

from moneylab.blocks import default_blocks

st.set_page_config(
    page_title="MoneyLab | Understand your money",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1100px; padding-top: 1.8rem; padding-bottom: 4rem;}
      h1, h2, h3 {letter-spacing: -0.025em;}
      h1 {font-weight: 750;}
      [data-testid="stMetric"] {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,.17);
        border-radius: 14px;
        padding: 1rem;
      }
      [data-testid="stMetricLabel"] {font-size: .86rem;}
      [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: .65rem;
      }
      div[data-testid="stButton"] button {border-radius: 10px;}
    </style>
    """,
    unsafe_allow_html=True,
)

if "ml_blocks" not in st.session_state:
    st.session_state.ml_blocks = []
if "ml_saved_scenarios" not in st.session_state:
    st.session_state.ml_saved_scenarios = []

home = st.Page("pages/0_Home.py", title="Home", icon="🏠", default=True)
money = st.Page("pages/1_My_Money.py", title="My Money", icon="💼", url_path="money")
goals = st.Page("pages/2_Goals.py", title="Goals", icon="🎯", url_path="goals")
explore = st.Page("pages/3_Explore.py", title="Explore", icon="🧪", url_path="explore")
learn = st.Page("pages/4_Learn.py", title="Learn", icon="🎓", url_path="learn")
settings = st.Page(
    "pages/6_Settings.py", title="Settings & data",
    icon="⚙️", url_path="settings", visibility="hidden",
)
classic = st.Page(
    "pages/2_Classic_Simulator.py", title="Classic simulator",
    icon="🧮", url_path="classic", visibility="hidden",
)

current_page = st.navigation(
    [home, money, goals, explore, learn, settings, classic],
    position="sidebar",
    expanded=True,
)

def load_sample_profile():
    st.session_state.ml_blocks = default_blocks()
    st.session_state.ml_saved_scenarios = []


def clear_financial_profile():
    st.session_state.ml_blocks = []
    st.session_state.ml_saved_scenarios = []


with st.sidebar:
    st.caption("UNDERSTAND YOUR MONEY. ENJOY YOUR LIFE.")
    with st.expander("Planning horizon & examples"):
        st.slider(
            "Projection months", 1, 120, 24,
            key="ml_months",
        )
        st.button(
            "Load optional example profile", use_container_width=True,
            key="ml_load_example", on_click=load_sample_profile,
        )
        st.button(
            "Start with an empty profile", use_container_width=True,
            key="ml_clear_profile", on_click=clear_financial_profile,
        )
    st.page_link(settings, label="Settings & data", icon="⚙️")
    st.page_link(classic, label="Classic simulator", icon="🧮")
    st.caption(
        "Manual-first planning. No connected bank accounts. "
        "Export your workspace to keep a copy."
    )

current_page.run()
