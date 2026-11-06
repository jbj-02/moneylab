"""Small, opt-in feedback form. No raw financial session data is attached."""
import os
import streamlit as st
from moneylab.feedback import feedback_draft, submit_private_feedback, validate_feedback


def _private_url():
    try:
        return st.secrets.get("MONEYLAB_FEEDBACK_URL", "") or os.environ.get(
            "MONEYLAB_FEEDBACK_URL", ""
        )
    except (FileNotFoundError, KeyError):
        return os.environ.get("MONEYLAB_FEEDBACK_URL", "")


def render_feedback():
    st.title("Share feedback")
    st.caption("Three short questions to help improve the MoneyLab alpha.")
    st.info(
        "Please do not enter real financial amounts, account details, "
        "names, addresses, or other identifying information. "
        "No figures from your MoneyLab profile or decisions are attached."
    )
    with st.form("alpha_private_feedback"):
        trying = st.text_area(
            "What were you trying to do?",
            max_chars=400, placeholder="I was comparing two apartments...",
        )
        problem = st.text_area(
            "What was confusing or went wrong?",
            max_chars=1200, placeholder="I couldn't find where...",
        )
        better = st.text_area(
            "What would have helped?",
            max_chars=800, placeholder="An explanation of...",
        )
        pressed = st.form_submit_button(
            "Send private feedback", type="primary",
            use_container_width=True,
        )
    answers = {"trying": trying, "problem": problem, "better": better}
    endpoint = _private_url()
    if endpoint:
        st.caption(
            "When you submit, these three answers are sent to a private "
            "Formspree inbox controlled by the app owner. They are not "
            "posted to public GitHub. Formspree processes this feedback."
        )
    else:
        st.warning(
            "Private delivery is not configured yet. Clicking Send will "
            "**not** transmit your feedback. You can instead download a "
            "draft to share privately with the app owner."
        )
    if pressed:
        try:
            if not endpoint:
                st.error("Feedback was not sent: a private inbox is not configured.")
            else:
                submit_private_feedback(answers, endpoint)
                st.success("Feedback delivered to the configured private inbox.")
        except ValueError as exc:
            st.error(str(exc))
    try:
        file_text = feedback_draft(answers)
    except ValueError:
        file_text = None
    st.download_button(
        "Download feedback draft (not submitted)",
        data=file_text or "MoneyLab alpha feedback\n",
        file_name="moneylab-alpha-feedback.txt",
        mime="text/plain", disabled=file_text is None,
    )
    st.page_link("pages/0_Home.py", label="Back to MoneyLab", icon="🏠")
