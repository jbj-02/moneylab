"""Explainable actions, alternatives and uncertainty, without presentation state.

Independent options are never accumulated into an allocation. Every option is a
new simulation of the same profile; committing one invalidates the others.
"""
from decimal import Decimal, ROUND_HALF_UP

from moneylab.blocks import ASSET_KINDS, project_blocks, serialize_blocks
from moneylab.engine import CENT, ZERO, calculate_monthly_loan_payment, validate_money
from moneylab.planning import goal_alternative, plan_actions, preview, signature
from moneylab.scenario_changes import apply_scenario_changes

FOCUSES = {
    "balanced": "Balance my priorities",
    "goals": "Reach a goal sooner",
    "cash": "Keep a cash cushion",
    "interest": "Pay less interest",
}
DEFAULT_PREFERENCE = {"focus": "balanced", "goal_id": None, "cash_floor": "0.00"}
MISSING_LABELS = {
    "income": "take-home income", "housing": "housing costs", "food": "food spending",
    "transport": "transport costs", "bills": "regular bills", "other": "other spending",
    "checking": "checking/cash balance", "savings": "savings balance", "debts": "debts and payments",
}


def validate_preference(value):
    if not isinstance(value, dict) or set(value) != {"focus", "goal_id", "cash_floor"}:
        raise ValueError("Unsupported action preference.")
    if not isinstance(value["focus"], str) or value["focus"] not in FOCUSES:
        raise ValueError("Choose an action priority.")
    goal_id = value["goal_id"]
    if goal_id is not None and (not isinstance(goal_id, str) or len(goal_id) > 64):
        raise ValueError("Choose a valid goal preference.")
    floor = validate_money(value["cash_floor"], "Cash cushion")
    if floor > Decimal("1000000000000"):
        raise ValueError("Cash cushion is too large.")
    return {"focus": value["focus"], "goal_id": goal_id, "cash_floor": str(floor)}


def _money(value):
    return f"${value:,.2f}" if value >= 0 else f"-${abs(value):,.2f}"


def first_reached(projection, goal):
    return next((r["month"] for r in projection["monthly_records"]
                 if r["balances"].get(goal["id"], ZERO) >= Decimal(goal["target"])), None)


def _forecast(blocks, horizon):
    return project_blocks(blocks, max([horizon, *[b["target_months"] for b in blocks if b["kind"] == "goal"]]))


def comparison_effects(comparison, *, horizon=120):
    """Compare goals at both their own deadlines and a common checkpoint."""
    original, alternative = comparison.get("comparison_source_blocks", comparison["source_blocks"]), comparison["blocks"]
    horizon = max(horizon, comparison["baseline"]["summary"]["months"])
    before, after = _forecast(original, horizon), _forecast(alternative, horizon)
    old = {g["id"]: g for g in original if g["kind"] == "goal"}
    impacts = []
    for goal in (g for g in alternative if g["kind"] == "goal" and g["id"] in old):
        previous = old[goal["id"]]
        checkpoint = previous["target_months"]
        original_funds = before["monthly_records"][checkpoint]["balances"][goal["id"]]
        alternative_funds = after["monthly_records"][checkpoint]["balances"][goal["id"]]
        deadline_funds = after["monthly_records"][goal["target_months"]]["balances"][goal["id"]]
        impacts.append({
            "id": goal["id"], "name": goal["name"], "checkpoint": checkpoint,
            "before": original_funds, "after": alternative_funds,
            "change": alternative_funds - original_funds,
            "target_before": Decimal(previous["target"]), "target_after": Decimal(goal["target"]),
            "deadline_before": checkpoint, "deadline_after": goal["target_months"],
            "at_new_deadline": deadline_funds, "on_track": deadline_funds >= Decimal(goal["target"]),
            "completion_before": first_reached(before, previous),
            "completion_after": first_reached(after, goal),
        })
    # Cash, debt and interest comparisons use the displayed comparison horizon.
    b, a = comparison["baseline"], comparison["alternative"]
    first_gap = next((r for r in a["monthly_records"][1:] if r["unfunded_shortfall"] > ZERO), None)
    return {
        "goals": impacts, "searched_months": before["summary"]["months"],
        "cash_before": b["summary"]["ending_cash_savings"], "cash_after": a["summary"]["ending_cash_savings"],
        "min_cash_before": min(r["cash_position"] for r in b["monthly_records"]),
        "min_cash_after": min(r["cash_position"] for r in a["monthly_records"]),
        "debt_change": a["summary"]["ending_debt"] - b["summary"]["ending_debt"],
        "interest_change": a["summary"]["total_interest"] - b["summary"]["total_interest"],
        "shortfall_month": first_gap["month"] if first_gap else None,
        "shortfall": first_gap["unfunded_shortfall"] if first_gap else ZERO,
        "months": b["summary"]["months"],
    }


def _goal_transfers(blocks, projection, goal_id, months):
    goal = next(b for b in blocks if b["id"] == goal_id)
    rate = Decimal(goal["annual_rate"])
    amounts = []
    for month in range(1, months + 1):
        old = projection["monthly_records"][month - 1]["balances"][goal_id]
        row = projection["monthly_records"][month]
        growth = (old * rate / Decimal(1200)).quantize(CENT, rounding=ROUND_HALF_UP)
        amounts.append(row["balances"][goal_id] - old - growth - row["direct_deposits"].get(goal_id, ZERO))
    return amounts


def funding_breakdown(comparison, goal_id=None):
    before, after = comparison["baseline"], comparison["alternative"]
    b, a = before["summary"], after["summary"]
    released = max(b["monthly_expenses"] - a["monthly_expenses"], ZERO)
    result = {
        "income": b["monthly_income"], "expenses": b["monthly_expenses"],
        "debt_payments": b["first_month_loan_payments"], "saving": b["first_month_transfers"],
        "remainder_before": before["monthly_records"][1]["net_cash_flow"],
        "remainder_after": after["monthly_records"][1]["net_cash_flow"],
        "released": released, "goal_increase": ZERO, "goal_change": ZERO, "from_released": ZERO,
        "from_remainder": ZERO, "released_left": released,
    }
    if goal_id:
        old = next(b for b in comparison["source_blocks"] if b["id"] == goal_id)
        goal = next(b for b in comparison["blocks"] if b["id"] == goal_id)
        extra = max(Decimal(goal["monthly_contribution"]) - Decimal(old["monthly_contribution"]), ZERO)
        directed = min(extra, released)
        amounts = _goal_transfers(comparison["blocks"], after, goal_id, goal["target_months"])
        result.update({
            "goal_increase": extra, "goal_change": Decimal(goal["monthly_contribution"]) - Decimal(old["monthly_contribution"]),
            "from_released": directed,
            "from_remainder": extra - directed, "released_left": released - directed,
            "requested": Decimal(goal["monthly_contribution"]),
            "first_month_funded": amounts[0],
            "direct_goal_deposit": after["monthly_records"][1]["direct_deposits"].get(goal_id, ZERO),
            "first_month_total_goal_funding": amounts[0] + after["monthly_records"][1]["direct_deposits"].get(goal_id, ZERO),
            "fully_funded_months": sum(v >= Decimal(goal["monthly_contribution"]) for v in amounts),
            "months": len(amounts),
        })
    return result


def explain_option(comparison, goal_id=None):
    effects, funding = comparison_effects(comparison), funding_breakdown(comparison, goal_id)
    tradeoffs = [f"Checking/cash at month {effects['months']}: {_money(effects['cash_before'])} → {_money(effects['cash_after'])}."]
    for goal in effects["goals"]:
        if goal["id"] != goal_id and (goal["change"] or goal["completion_before"] != goal["completion_after"]):
            timing = (f"Target timing: month {goal['completion_before']} → month {goal['completion_after']}."
                      if goal["completion_before"] is not None and goal["completion_after"] is not None
                      else f"A target may remain unreached within {effects['searched_months']} months.")
            tradeoffs.append(f"{goal['name']}: {_money(goal['before'])} → {_money(goal['after'])} at month {goal['checkpoint']}. {timing}")
    if effects["debt_change"] or effects["interest_change"]:
        tradeoffs.append(f"Ending debt changes by {_money(effects['debt_change'])}; modeled interest changes by {_money(effects['interest_change'])} over {effects['months']} months.")
    # Include affected non-goal accounts, not just the headline target.
    goals = {g["id"] for g in effects["goals"]}
    before_last, after_last = comparison["baseline"]["monthly_records"][-1], comparison["alternative"]["monthly_records"][-1]
    for account in comparison["source_blocks"]:
        ident = account["id"]
        if account["kind"] in ASSET_KINDS and ident not in goals:
            delta = after_last["balances"].get(ident, ZERO) - before_last["balances"].get(ident, ZERO)
            if delta:
                tradeoffs.append(f"{account['name']} changes by {_money(delta)} at month {effects['months']}.")
    if effects["shortfall_month"]:
        tradeoffs.append(f"Unfunded costs start in month {effects['shortfall_month']} with a gap of {_money(effects['shortfall'])}.")
    goal = next((g for g in effects["goals"] if g["id"] == goal_id), None)
    return {"effects": effects, "funding": funding, "tradeoffs": tradeoffs, "goal": goal}


def goal_options(blocks, goal_id):
    """A few distinct paths, all evaluated by the engine against one source."""
    plan = plan_actions(blocks, reviewed=True)
    if goal_id not in plan["goals"]:
        raise ValueError("Choose a goal that still exists in your profile.")
    outlook = plan["goals"][goal_id]
    goal = next(b for b in serialize_blocks(blocks) if b["id"] == goal_id)
    current = preview(blocks, blocks, title="Keep the current contribution")
    choices = [{"key": "current", "title": "Keep my current pace", "comparison": current}]
    if not outlook["on_track"] and outlook["required"] is not None:
        choices.append({"key": "deadline", "title": "Save more to meet the deadline",
                        "comparison": goal_alternative(blocks, goal_id, outlook["required"])})
    forecast = _forecast(serialize_blocks(blocks), 120)
    completion = first_reached(forecast, goal)
    if completion is not None and completion > goal["target_months"]:
        choices.append({"key": "later", "title": "Give myself more time",
                        "comparison": goal_alternative(blocks, goal_id, goal["monthly_contribution"], deadline=completion)})
    affordable_target = outlook["projected"]
    if ZERO < affordable_target < outlook["target"]:
        choices.append({"key": "target", "title": "Choose a smaller target",
                        "comparison": goal_alternative(blocks, goal_id, goal["monthly_contribution"], target=affordable_target)})
    for option in choices:
        option["comparison"]["title"] = f"{goal['name']}: {option['title'].lower()}"
        option["analysis"] = explain_option(option["comparison"], goal_id)
    return choices


def build_action_plan(blocks, *, reviewed=False, preference=None, missing=(), months=24):
    preference = validate_preference(preference or DEFAULT_PREFERENCE)
    plan = plan_actions(blocks, reviewed=reviewed, months=months)
    items = serialize_blocks(blocks)
    baseline = plan["projection"]
    actions = plan["actions"]
    if preference["focus"] == "interest":
        loans = [b for b in items if b["kind"] == "loan" and Decimal(b["balance"]) > 0 and Decimal(b["annual_rate"]) > 0]
        if loans:
            loan = max(loans, key=lambda b: Decimal(b["annual_rate"]))
            if not any(a["kind"] == "debt" and loan["id"] == a.get("loan_id") for a in actions):
                actions = [a for a in actions if a["kind"] != "maintain"]
                actions.append({"kind": "interest", "loan_id": loan["id"], "title": f"Compare paying {loan['name']} faster",
                                "detail": f"You chose to reduce interest. This loan's entered annual rate is {loan['annual_rate']}%."})
    floor = Decimal(preference["cash_floor"])
    if preference["focus"] == "cash" and baseline["monthly_records"][0]["cash_savings"] < floor:
        actions = [a for a in actions if a["kind"] != "maintain"]
        cash = baseline["monthly_records"][0]["cash_savings"]
        actions.append({"kind": "reserve", "title": "Build the checking cushion you chose",
                        "cash_floor": floor,
                        "detail": f"Recorded checking/cash is {_money(cash)}, {_money(floor - cash)} below your {_money(floor)} preference."})

    def rank(action):
        kind = action["kind"]
        if kind == "shortfall": return (0, 0, 0)
        if kind == "debt": return (1, 0, 0)
        if kind == "review": return (2, 0, 0)
        if kind == "reserve": return (3, 0, 0)
        if kind == "interest": return (3, 1, 0)
        if kind == "goal":
            chosen = preference["focus"] in ("goals", "cash") and action["goal_id"] == preference["goal_id"]
            return (4, 0 if chosen else 1, action["outlook"]["deadline"])
        return (5, 0, 0)

    actions = sorted(actions, key=rank)
    assumptions = ["Income, spending and entered rates repeat; daily bill timing, taxes and surprises are excluded.",
                   "Available monthly money funds accounts in saved order. Independent options may need the same money."]
    if not reviewed:
        assumptions.insert(0, "Preliminary: figures have not been confirmed complete.")
    if missing:
        assumptions.insert(0, "Not yet confirmed: " + ", ".join(MISSING_LABELS.get(k, k) for k in missing) + ".")
    for action in actions:
        kind = action["kind"]
        action["id"] = f"{kind}:{action.get('goal_id', action.get('loan_id', action['title']))}"
        action["finding"] = action["detail"]
        action["assumptions"] = assumptions
        action["rank_reason"] = {
            "shortfall": "An upcoming cash shortfall can leave recorded obligations unfunded, so it comes before optional goals.",
            "debt": "A growing balance means the recorded payment is below monthly interest; this risk comes before optional goal changes.",
            "review": "Missing or unreviewed figures can change both the funding available and the order of priorities.",
            "interest": "You chose to reduce interest, so a comparison for the highest entered loan rate comes before optional goal adjustments.",
            "reserve": "You chose to protect checking/cash, and the recorded balance is below your chosen cushion.",
            "maintain": "No modeled cash shortfall, growing loan or missed goal deadline was found in the assessed horizon.",
        }.get(kind, "Among goal gaps, the nearer deadline comes first.")
        if kind == "goal" and preference["focus"] in ("goals", "cash") and action["goal_id"] == preference["goal_id"]:
            action["rank_reason"] = "You selected this goal as your priority. Cash shortfalls, growing debt and incomplete figures still come first."
    plan.update(actions=actions, preference=preference)
    return plan


def action_breakdown(blocks, action):
    """Compute the recommended candidate and its supporting explanation lazily."""
    kind = action["kind"]
    result = {**action, "comparison": None, "analysis": None}
    baseline = project_blocks(blocks, 24)
    summary = baseline["summary"]
    reason = (f"Recorded take-home {_money(summary['monthly_income'])} − living costs {_money(summary['monthly_expenses'])} "
              f"− debt payments {_money(summary['first_month_loan_payments'])} − funded savings {_money(summary['first_month_transfers'])} "
              f"leaves {_money(baseline['monthly_records'][1]['net_cash_flow'])} in month 1.")
    proposed = "Review and update the recorded figures before changing commitments."
    outcome = "More complete figures allow a more reliable comparison."
    if kind == "goal":
        outlook = action["outlook"]
        amount = outlook["required"] if outlook["required"] is not None else outlook["planned"]
        comparison = goal_alternative(blocks, action["goal_id"], amount)
        analysis = explain_option(comparison, action["goal_id"])
        result.update(comparison=comparison, analysis=analysis)
        goal = next(b for b in serialize_blocks(blocks) if b["id"] == action["goal_id"])
        direct = baseline["monthly_records"][1]["direct_deposits"].get(action["goal_id"], ZERO)
        reason += (f" {_money(outlook['starting'])} already saved, {_money(outlook['planned'])}/month planned and entered interest "
                   f"produce {_money(outlook['projected'])} by month {outlook['deadline']}, against a {_money(outlook['target'])} target.")
        reason += f" The entered illustrative annual rate is {goal['annual_rate']}%."
        if direct:
            reason += f" This also includes {_money(direct)}/month of recorded direct deposits to the goal."
        if outlook["required"] is not None:
            proposed = f"Compare saving {_money(amount)}/month, an increase of {_money(outlook['extra'])}."
        else:
            proposed = "Compare keeping the current pace, a later deadline, a smaller target or an expense reduction you select."
        goal = analysis["goal"]
        timing = f"month {goal['completion_after']}" if goal["completion_after"] is not None else f"not reached within {analysis['effects']['searched_months']} months"
        outcome = f"Projected target timing: {timing}; {_money(goal['at_new_deadline'])} at the current deadline."
    elif kind in ("debt", "interest"):
        loans = [b for b in serialize_blocks(blocks) if b["kind"] == "loan"]
        loan = (next((b for b in loans if b["id"] == action["loan_id"]), None) if action.get("loan_id")
                else next((b for b in loans if b["name"] in action["title"]), None))
        if loan:
            payment = Decimal(loan["monthly_payment"])
            interest = calculate_monthly_loan_payment(loan["balance"], loan["annual_rate"], payment)["monthly_interest"]
            extra = max(interest + CENT - payment, ZERO) if kind == "debt" else summary["unallocated_monthly_buffer"]
            if extra > ZERO:
                alternative = serialize_blocks(blocks)
                next(b for b in alternative if b["id"] == loan["id"])["monthly_payment"] = str(payment + extra)
                comparison = preview(blocks, alternative, title=f"A different payment for {loan['name']}")
                result.update(comparison=comparison, analysis=explain_option(comparison))
                proposed = f"Compare a {_money(payment + extra)} monthly payment ({_money(extra)} more)."
                outcome = f"Modeled interest changes by {_money(result['analysis']['effects']['interest_change'])} over {result['analysis']['effects']['months']} months."
            else:
                proposed = "No recorded monthly remainder is available for an extra payment. Compare a change to an expense you choose."
                outcome = "An extra payment needs a funding change; no additional income or borrowing is assumed."
    elif kind == "shortfall":
        proposed = "Choose a recorded expense or income assumption to compare. The model already limits savings transfers when cash is unavailable."
        outcome = "Compare whether that change removes the shortfall without delaying another priority."
    elif kind == "reserve":
        comparison = preview(blocks, blocks, title="Keep the recorded monthly remainder in checking")
        result.update(comparison=comparison, analysis=explain_option(comparison))
        reserve = project_blocks(blocks, 120)
        month = next((r["month"] for r in reserve["monthly_records"] if r["cash_savings"] >= action["cash_floor"]), None)
        proposed = "Compare keeping the recorded monthly remainder in checking before increasing other commitments. No new money or expense reduction is assumed."
        outcome = (f"The chosen {_money(action['cash_floor'])} checking cushion is first reached in month {month} in this model."
                   if month is not None else f"The chosen {_money(action['cash_floor'])} checking cushion is not reached within 120 months.")
    elif kind == "maintain":
        comparison = preview(blocks, blocks, title="Keep the recorded plan")
        result.update(comparison=comparison, analysis=explain_option(comparison))
        proposed = "Keep the recorded plan, or stress-test a decision before changing it."
        outcome = "Update balances to compare later progress with a plan you explicitly choose."
    result.update(reason=reason, proposed_action=proposed, outcome=outcome)
    return result


def _dashboard_option(option):
    analysis = option["analysis"]
    goal, funding = analysis["goal"], analysis["funding"]
    title = option["title"]
    if option["key"] == "deadline":
        title = f"Save {_money(funding['requested'])}/month for {goal['name']}"
    elif option["key"] == "later":
        title = f"Keep {_money(funding['requested'])}/month; allow {goal['deadline_after']} months"
    elif option["key"] == "target":
        title = f"Aim for {_money(goal['target_after'])} by month {goal['deadline_after']}"
    elif option["key"] == "current":
        title = f"Keep saving {_money(funding['requested'])}/month"
    if option["key"] == "target":
        benefit = (f"Meet a smaller {_money(goal['target_after'])} target by month {goal['deadline_after']}, "
                   f"keeping {_money(funding['requested'])}/month.")
    elif goal["completion_after"] is None:
        benefit = f"The target is not reached within {analysis['effects']['searched_months']} months."
    elif goal["completion_before"] is not None and goal["completion_after"] < goal["completion_before"]:
        benefit = (f"Reach {_money(goal['target_after'])} in {goal['completion_after']} months instead of "
                   f"{goal['completion_before']} — {goal['completion_before'] - goal['completion_after']} months sooner.")
    else:
        benefit = f"Reach the {_money(goal['target_after'])} target in about {goal['completion_after']} months."
    warnings = []
    if not goal["on_track"]:
        warnings.append(f"Still {_money(max(goal['target_after'] - goal['at_new_deadline'], ZERO))} short at the month-{goal['deadline_after']} deadline.")
    if funding["goal_increase"]:
        if funding["from_remainder"] <= max(funding["remainder_before"], ZERO):
            source = (f"Use {_money(funding['from_remainder'])} of the {_money(max(funding['remainder_before'], ZERO))} "
                      "left each month after recorded bills, debt payments and saving.")
        else:
            source = (f"The increase needs {_money(funding['goal_increase'])}/month; the current remainder is "
                      f"{_money(funding['remainder_before'])}. It may reduce funding elsewhere.")
        if funding["from_released"]:
            source += f" Redirect {_money(funding['from_released'])} from the selected expense reduction."
    else:
        source = f"Keep the existing {_money(funding['requested'])} contribution; no extra monthly saving is requested."
    if funding["direct_goal_deposit"]:
        source += f" The recorded {_money(funding['direct_goal_deposit'])} direct deposit also continues."
    source += f" The first-month cash remainder would be {_money(funding['remainder_after'])}."
    if funding["fully_funded_months"] < funding["months"]:
        warnings.append(f"The full contribution is funded in only {funding['fully_funded_months']} of {funding['months']} months.")
    for other in analysis["effects"]["goals"]:
        if other["id"] != goal["id"] and other["change"] < ZERO:
            warnings.append(f"{other['name']} has {_money(-other['change'])} less at its original deadline.")
    if analysis["effects"]["shortfall_month"]:
        warnings.append(f"Unfunded cash starts in month {analysis['effects']['shortfall_month']}.")
    if option["key"] == "target":
        warnings.append("This lowers the goal; it does not create additional money.")
    return {**option, "headline": title, "benefit": benefit, "funding_source": source,
            "warnings": warnings, "completion_month": goal["completion_after"]}


def dashboard_action(blocks, plan):
    """Put one proposal and two honest alternatives on the dashboard itself.

    Missing review is a visible qualifier, not an extra gate to understanding
    a preliminary option. Actual cash/debt risk ordering remains unchanged.
    """
    action = next((a for a in plan["actions"] if a["kind"] != "review"), plan["actions"][0])
    detail = action_breakdown(blocks, action)
    if action["kind"] == "goal":
        options = goal_options(blocks, action["goal_id"])
        by_key = {o["key"]: o for o in options}
        key = "deadline" if "deadline" in by_key else "later" if "later" in by_key else "current"
        chosen = _dashboard_option(by_key[key])
        alternatives = [_dashboard_option(by_key[k]) for k in ("later", "target", "current") if k != key and k in by_key][:2]
        if len(alternatives) < 2:
            alternatives.append({"key": "custom", "headline": "Choose an expense or saving change",
                                 "benefit": "Compare a reduction you select against this goal and the rest of your plan.",
                                 "funding_source": "Only recorded expenses are offered. Choose the amount before a benefit is estimated.",
                                 "warnings": [], "comparison": None, "completion_month": None})
        if len(alternatives) < 2:
            alternatives.append({"key": "review", "headline": "Review the recorded figures",
                                 "benefit": "A second funded alternative is not supported by the current figures.",
                                 "funding_source": "Update figures that changed, or confirm missing information. No extra money is assumed.",
                                 "warnings": [], "comparison": None, "completion_month": None})
        detail.update(comparison=chosen["comparison"], analysis=chosen["analysis"],
                      proposed_action=chosen["headline"], outcome=chosen["benefit"])
        return {"action": action, "detail": detail, "recommended": chosen, "alternatives": alternatives}
    candidate = detail["comparison"]
    funding = (f"The first-month remainder would be {_money(detail['analysis']['funding']['remainder_after'])}; "
               "the full comparison shows other commitments." if candidate else
               "No additional money is assumed. Choose a recorded change before committing more money.")
    recommended = {"key": "action", "headline": action["title"], "benefit": detail["outcome"],
                   "funding_source": funding, "warnings": [], "completion_month": None, "comparison": candidate}
    current = preview(blocks, blocks, title="Keep the recorded plan")
    rows = current["baseline"]["monthly_records"]
    gap = next((r for r in rows[1:] if r["unfunded_shortfall"] > 0), None)
    current_result = (f"Unfunded cash of {_money(gap['unfunded_shortfall'])} still starts in month {gap['month']}."
                      if gap else f"First-month cash remainder stays {_money(rows[1]['net_cash_flow'])}.")
    alternatives = [
        {"key": "current", "headline": "Keep the current plan", "benefit": current_result,
         "funding_source": "No contribution, expense or payment changes.", "warnings": [],
         "comparison": current, "completion_month": None},
        {"key": "custom", "headline": "Choose a recorded adjustment", "benefit": "Test an expense, income or payment change you enter.",
         "funding_source": "The outcome is calculated after you choose the change; no reduction or extra income is assumed.",
         "warnings": [], "comparison": None, "completion_month": None},
    ]
    return {"action": action, "detail": detail, "recommended": recommended, "alternatives": alternatives}


def stress_test(comparison, change):
    """Apply the same explicit shock to both plans. Never create an approvable plan."""
    results = {}
    for key, blocks in (("current", comparison.get("comparison_source_blocks", comparison["source_blocks"])), ("chosen", comparison["blocks"])):
        applied = dict(change)
        if change.get("operation") == "adjust_monthly":
            if set(change) != {"operation", "block_id", "delta"}:
                raise ValueError("A monthly stress needs a recorded item and an explicit change.")
            item = next((b for b in blocks if b["id"] == change["block_id"] and b["kind"] in ("income", "expense")), None)
            if item is None:
                raise ValueError("Choose an existing income or expense to stress-test.")
            try:
                delta = Decimal(str(change["delta"]))
            except ArithmeticError:
                raise ValueError("Enter a finite monthly stress amount.") from None
            if not delta.is_finite():
                raise ValueError("Enter a finite monthly stress amount.")
            applied = {"operation": "set_monthly", "block_id": item["id"],
                       "amount": str(Decimal(item["monthly_amount"]) + delta)}
        try:
            stressed = apply_scenario_changes(blocks, [applied])
            results[key] = {"projection": project_blocks(stressed, comparison["baseline"]["summary"]["months"]),
                            "blocks": serialize_blocks(stressed), "error": None}
        except ValueError as exc:
            if change.get("operation") != "one_time_cash":
                raise
            # An unfunded upfront cost is reported, never silently financed.
            cash = sum((Decimal(b["balance"]) for b in blocks if b["kind"] == "cash"), ZERO)
            results[key] = {"projection": None, "blocks": None, "error": str(exc),
                            "upfront_gap": max(validate_money(change["amount"], "Stress cost") - cash, ZERO)}
    return {"allow_apply": False, "source_signature": comparison["source_signature"],
            "candidate_signature": signature(comparison["blocks"]), "change": dict(change), **results}
