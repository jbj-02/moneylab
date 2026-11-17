"""MoneyLab's plan-first shell; the Python engine has no UI dependency."""
import streamlit as st

from moneylab.design import theme
from moneylab.plan_session import load_example, sync_local

st.set_page_config(page_title="MoneyLab | A plan for what comes next", page_icon="◒",
                   layout="wide", initial_sidebar_state="auto")
theme()
sync_local()
if "ml_blocks" not in st.session_state:
    st.session_state.ml_blocks = []
if "ml_saved_scenarios" not in st.session_state:
    st.session_state.ml_saved_scenarios = []

home = st.Page("pages/0_Home.py", title="My Plan", default=True)
money = st.Page("pages/1_My_Money.py", title="Edit figures", url_path="money")
explore = st.Page("pages/3_Explore.py", title="Can I buy this?", url_path="explore")
moving = st.Page("pages/7_Moving_Out_Alpha.py", title="Plan a move", url_path="moving-alpha")
settings = st.Page("pages/6_Settings.py", title="Settings & data", url_path="settings", visibility="hidden")
# Existing bookmarks stay reachable; old tools leave the primary experience.
hidden = [
    st.Page("pages/10_Action_Plan.py", title="What should I do?", url_path="actions", visibility="hidden"),
    st.Page("pages/9_Compare_Plan.py", title="Compare your plan", url_path="compare", visibility="hidden"),
    st.Page("pages/2_Goals.py", title="Goals", url_path="goals", visibility="hidden"),
    st.Page("pages/12_More_Decisions.py", title="Other plan changes", url_path="other-changes", visibility="hidden"),
    st.Page("pages/13_Detailed_Move.py", title="Detailed move tools", url_path="move-details", visibility="hidden"),
    st.Page("pages/5_Quick_Start.py", title="Build your plan", url_path="quick-start", visibility="hidden"),
    st.Page("pages/4_Learn.py", title="Learn", url_path="learn", visibility="hidden"),
    st.Page("pages/2_Classic_Simulator.py", title="Classic simulator", url_path="classic", visibility="hidden"),
    st.Page("pages/8_Feedback.py", title="Feedback", url_path="feedback", visibility="hidden"),
]
with st.sidebar:
    st.markdown('<div class="ml-brand">◒ MoneyLab</div>', unsafe_allow_html=True)
    st.caption("A plan for what comes next.")
current_page = st.navigation([home, explore, moving, money, settings, *hidden], position="sidebar")


with st.sidebar:
    st.divider()
    st.caption(st.session_state.get("ml_save_status", "Session only · download a backup"))
    if st.session_state.get("ml_store_error"):
        st.warning("Local saving is unavailable or another session changed the plan. Download a backup before reloading.")
    st.page_link(settings, label="Settings & data")
    with st.expander("Try fictional figures"):
        if st.session_state.ml_blocks:
            st.checkbox("Replace my current profile with fictional sample data", key="ml_example_confirm")
        st.button("Load optional example profile", key="ml_load_example", on_click=load_example,
                  disabled=bool(st.session_state.ml_blocks) and not st.session_state.get("ml_example_confirm", False))
    st.caption("Educational planning with your figures. No bank connection.")

current_page.run()
sync_local()
