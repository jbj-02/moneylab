"""MoneyLab — understand your money, enjoy your life.

Native Streamlit navigation keeps financial decisions and optional setup approachable. Actual
calculations, financial blocks and state are provided by moneylab.ui_app.
"""

import streamlit as st

from moneylab.blocks import default_blocks

st.set_page_config(
    page_title="MoneyLab | Understand your money",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1000px; padding-top: 1.8rem; padding-bottom: 4rem;}
      h1, h2, h3 {letter-spacing: -0.025em;}
      h1 {font-weight: 750;}
      [data-testid="stMetric"] {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,.17);
        border-radius: 8px;
        padding: 1rem;
      }
      [data-testid="stMetricLabel"] {font-size: .86rem;}
      [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: .65rem;
      }
      div[data-testid="stButton"] button,
      div[data-testid="stFormSubmitButton"] button,
      div[data-testid="stDownloadButton"] button {
        border-radius: 10px;
        min-height: 2.75rem;
      }
      [data-testid="stExpander"] {border-radius: 12px;}
      [data-testid="stWidgetLabel"] p {line-height: 1.45;}
      [data-testid="stCaptionContainer"] {font-size: .95rem; line-height: 1.55;}
      [data-testid="stCaptionContainer"] p {color: var(--text-color); opacity: .82;}
      [data-testid="stProgress"] {margin: .5rem 0 1rem;}
      [data-testid="stDataFrame"] {max-width: 100%;}
      [data-testid="stSidebar"] .stPageLink a {
        min-height: 2.5rem;
      }
      div[data-testid="stButton"] button:focus-visible,
      div[data-testid="stLinkButton"] a:focus-visible {
        outline: 3px solid var(--primary-color, #4472c4);
        outline-offset: 3px;
      }
      @media (max-width: 768px) {
        .block-container {
          padding: 1rem 1rem 3.5rem;
          max-width: 100%;
        }
        [data-testid="stMetric"] {padding: .75rem;}
        [data-testid="stMetricValue"] {font-size: 1.45rem;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

if "ml_blocks" not in st.session_state:
    st.session_state.ml_blocks = []
if "ml_saved_scenarios" not in st.session_state:
    st.session_state.ml_saved_scenarios = []

moving_alpha = st.Page("pages/7_Moving_Out_Alpha.py", title="Move Out", icon="🏡", url_path="moving-alpha", visibility="hidden")

home = st.Page("pages/0_Home.py", title="My Plan", default=True)
money = st.Page("pages/1_My_Money.py", title="My Finances", url_path="money")
goals = st.Page("pages/2_Goals.py", title="Goals", url_path="goals", visibility="hidden")
explore = st.Page("pages/3_Explore.py", title="Explore Decisions", url_path="explore")
learn = st.Page("pages/4_Learn.py", title="Learn", icon="🎓", url_path="learn", visibility="hidden")
quick_start = st.Page(
    "pages/5_Quick_Start.py", title="Quick Start",
    icon="✨", url_path="quick-start", visibility="hidden",
)
settings = st.Page(
    "pages/6_Settings.py", title="Settings & data",
    icon="⚙️", url_path="settings", visibility="hidden",
)
classic = st.Page(
    "pages/2_Classic_Simulator.py", title="Classic simulator",
    icon="🧮", url_path="classic", visibility="hidden",
)
feedback = st.Page(
    "pages/8_Feedback.py", title="Feedback", icon="💬",
    url_path="feedback", visibility="hidden",
)

current_page = st.navigation(
    [home, money, explore, goals, moving_alpha, quick_start, learn, settings, classic, feedback],
    position="sidebar",
    expanded=True,
)

def _invalidate_profile_dependent_results():
    for key in (
        "move_result", "move_run_options", "move_inputs_at_run",
        "move_variant_result", "move_variant_inputs",
        "ml_reviewed_signature",
    ):
        st.session_state.pop(key, None)
    st.session_state.move_editing = True


def load_sample_profile():
    st.session_state.ml_blocks = default_blocks()
    st.session_state.ml_saved_scenarios = []
    st.session_state.ml_example_confirm = False
    _invalidate_profile_dependent_results()


def clear_financial_profile():
    st.session_state.ml_blocks = []
    st.session_state.ml_saved_scenarios = []
    _invalidate_profile_dependent_results()


with st.sidebar:
    st.caption("MONEYLAB")
    st.page_link(
        settings, label="Save / restore workspace",
        use_container_width=True,
    )
    st.page_link(
        feedback, label="Alpha feedback",
        use_container_width=True,
    )
    with st.expander("Examples & projection settings"):
        st.slider("Projection months", 1, 120, 24, key="ml_months")
        if st.session_state.ml_blocks:
            st.checkbox(
                "Replace my current profile with fictional sample data",
                key="ml_example_confirm",
            )
        st.button(
            "Load optional example profile",
            use_container_width=True,
            help="Fictional demonstration values. Requires confirmation "
                 "if your profile already has data.",
            key="ml_load_example", on_click=load_sample_profile,
            disabled=bool(st.session_state.ml_blocks) and not
                     st.session_state.get("ml_example_confirm", False),
        )
        confirm_reset = st.checkbox(
            "I want to clear my current profile",
            key="ml_confirm_reset",
        )
        st.button(
            "Start with an empty profile",
            use_container_width=True,
            key="ml_clear_profile", on_click=clear_financial_profile,
            disabled=not confirm_reset,
        )
    with st.expander("More tools"):
        st.page_link(quick_start, label="Guided setup")
        st.page_link(learn, label="Learn", icon="📚")
        st.page_link(classic, label="Classic simulator (legacy)", icon="🧮")
    st.caption(
        "Session only — not autosaved. Export a workspace to keep your "
        "figures and decision drafts."
    )

current_page.run()
