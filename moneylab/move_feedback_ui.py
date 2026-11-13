"""Decision-first move result using the existing moving and timing models."""
from decimal import Decimal

import streamlit as st

from moneylab.decision_feedback import goal_gap_changes
from moneylab.move_goal import move_goal_timing
from moneylab.move_goal_ui import _timing


def render_move_answer(report, inputs, calculate, options, money, write):
    st.subheader("What moving would change")
    missing = set(report["missing"])
    budget_missing = bool(missing.intersection(("other_living", "minimum_debt")))
    cash_missing = "checking" in missing
    if cash_missing:
        write(f"**Enter available checking to check the upfront cost.** "
              f"The move-in costs entered so far total {money(report['upfront'])}.")
    elif report["fundable"]:
        write(f"**The recorded move-in costs use {money(report['upfront'])} upfront.** "
              f"You’d have {money(report['remaining_liquid'])} in accessible cash and savings afterward.")
    else:
        write(f"**The move is {money(report['funding_gap'])} short upfront** at the recorded costs "
              f"of {money(report['upfront'])}, using only the funds you allowed.")
    contributions = report["details"]["planned_goal_contributions"]
    margin = report["monthly_margin_after"] - contributions
    if margin < 0:
        write(f"**The monthly budget is short by {money(-margin)}** after recorded bills, debt and planned goal transfers.")
    else:
        write(f"**{money(margin)} per month remains** after recorded bills, debt and planned goal transfers.")
    if report["missing"] or not report["reviewed"]:
        st.caption("Preliminary estimate. Missing costs can raise the amount needed up front or reduce the monthly remainder.")
    if budget_missing or cash_missing:
        write("**Next step:** Use Edit move to fill in your available cash, regular expenses or debt payments where missing.")
    elif margin < 0:
        rent = Decimal(str(inputs["rent"]))
        if rent > -margin:
            write(f"**Next step:** Test rent of {money(rent + margin)} or less to close the monthly gap, "
                  "with the other recorded amounts held fixed.")
        else:
            write("**Next step:** Review the monthly budget. Lower rent alone would not close this gap at the recorded amounts.")
    elif not report["fundable"]:
        write("**Next step:** Test a later move date or reduce your move-in costs.")
    else:
        write("**Next step:** Set the cash cushion you want to keep, then check whether you can move at your planned pace.")

    if report["proposed"]:
        for name, deadline, before, after in goal_gap_changes(report["baseline"], report["proposed"]):
            if before != after:
                write(f"**{name}:** The projected gap at month {deadline} changes from {money(before)} to {money(after)}.")
            elif before:
                write(f"**{name}:** The existing {money(before)} gap at month {deadline} stays the same.")

    st.markdown("#### Try a different plan")
    col1, col2 = st.columns(2)
    rent = Decimal(str(inputs["rent"]))
    with col1:
        alternative_rent = st.number_input("Lower monthly rent ($)", min_value=0.0,
                                           max_value=float(rent), value=None, step=25.0,
                                           key="move_quick_rent")
        if alternative_rent is not None and 0 < Decimal(str(alternative_rent)) < rent:
            try:
                alternative = calculate({**inputs, "rent": alternative_rent}, options)
                alternative_margin = alternative["monthly_margin_after"] - contributions
                write(f"At {money(alternative_rent)} rent, you’d have **{money(alternative_margin)}/month** "
                      f"after the same commitments, {money(alternative_margin - margin)} more than with the original rent.")
                write(f"Move-in costs stay at {money(report['upfront'])} in this comparison. "
                      "Edit the move if the deposit or fees would change.")
            except ValueError as exc:
                st.info(str(exc))
    with col2:
        cushion = st.number_input("Cash to keep after moving ($)", min_value=0.0,
                                  max_value=1e8, value=None, step=25.0, key="move_quick_cushion")
        monthly = st.number_input("Amount to save before moving ($/month)", min_value=0.0,
                                  max_value=1e8, value=None, step=25.0, key="move_quick_save")
        living = next(row["amount"] for row in report["details"]["current"]
                      if row["field"] == "other_living")
        cut = Decimal("0")
        if living > 0:
            cut = Decimal(str(st.number_input(
                "Optional monthly spending cut ($)", min_value=0.0, max_value=float(living),
                step=25.0, key="move_quick_cut",
                help="Choose a reduction you can make within the regular expenses already entered. "
                     "This assumes you keep the cut after moving.",
            )))
        if cushion is not None and monthly is not None and not cash_missing and not budget_missing:
            try:
                timing = move_goal_timing(report, monthly_savings=Decimal(str(monthly)),
                                          cushion=Decimal(str(cushion)), deadline=1)
                write(f"**{_timing(timing['months'])}** for move-in costs and your cushion "
                      f"if you save {money(monthly)} each month.")
                if cut:
                    revised = move_goal_timing(report, monthly_savings=Decimal(str(monthly)),
                                               cushion=Decimal(str(cushion)), deadline=1,
                                               spending_cut=cut)
                    write(f"With the {money(cut)} monthly cut: **{_timing(revised['months'])}**, "
                          f"with {money(revised['monthly_after'])}/month left after moving.")
                if timing["monthly_after"] < 0:
                    write(f"Waiting leaves the monthly shortfall of {money(-timing['monthly_after'])} after moving.")
            except ValueError as exc:
                st.info(str(exc))
