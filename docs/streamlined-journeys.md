# Streamlined task journeys

MoneyLab now gives savings, purchases and moving their own short paths. The sidebar has four destinations: **My Plan**, **Can I buy this?**, **Plan a move** and **Edit figures**. Settings has one footer link. Each result has one **See details** area for charts, assumptions and breakdowns; missing figures, funding problems and goal effects stay beside the answer.

## What changed

- **Savings:** returning users still see their goal, deadline, projected gap and one modeled adjustment immediately. The comparison now opens in place on My Plan, with a compact current/test table for goal balance, gap and monthly money. Four separate supporting disclosures became one. Back and Edit figures remain secondary.
- **Purchase:** the dedicated navigation item opens one form. A profile with recorded cash needs only the price, then **See impact**. Cash and goal effects appear on that route. A visitor without a profile needs only price and cash for a clearly labeled cash-only answer; the app explains that income, commitments and goals are needed for monthly impact.
- **Move:** recorded income, housing, debt, savings and cash are reused. An identifiable housing entry needs three figures: new rent share, net change in other monthly costs, and total upfront costs. The result leads with upfront costs and monthly money, then affected goals. A single modeled rental budget can be tested without replacing the plan. Back retains the tested assumptions.
- Removed the source/type/frequency selectors from straightforward purchases, the separate comparison route for the three core tasks, the move wizard and manual profile-load step from the primary path, repeated dashboard sections, duplicate backup links and low-risk figure-review confirmations. Existing recurring-cost, parser and detailed move tools remain optional; the Python engines and financial regression coverage remain in place.
- Applying remains explicit: the exact tested edits must pass source validation and the user must select the approval checkbox before Apply is enabled. Missing figures block applying. New tests check that changed source figures invalidate old results.

## Matched walkthrough measurement

Baseline: `bec32bc59c7f49faddfda5f5923dfcb58429211c`, the latest authored result-first version in PR #10. That branch was ahead of `main` when this work started. This change is stacked on that branch rather than silently merging it. Both versions were run locally in Chromium before and after implementation, at desktop **1440 × 1000** and mobile **390 × 844**, with the same fictional profile. These are branch validation captures, not a claim that the public deployment has changed.

| Journey to first useful answer | Screens before → after | New figures before → after | Desktop clicks before → after | Mobile clicks before → after |
| --- | --- | --- | --- | --- |
| See savings result | 1 → 1 | 0 → 0 | 0 → 0 | 0 → 0 |
| Test its suggested change | 2 → 1 | 0 → 0 | 1 → 1 | 1 → 1 |
| Check a purchase | 3 → 2 | 1 → 1 | 2 → 2 | 4 → 4 |
| Plan a move | 3 → 2 | 4 → 3 | 8 → 2 | 10 → 4 |
| Guest purchase, cash answer | 2 → 2 | 4 → 2 | 2 → 2 | 2 → 2 |

**Definitions:** screens are distinct task routes, including the starting My Plan screen; inline form/result states share a route. New figures count the scenario amounts entered for this matched case, excluding already saved profile figures and untouched defaults. Clicks count control activations, including navigation, disclosures and opening/closing the mobile drawer; typing, field focus and fixture setup are excluded. The savings test row starts at the displayed goal result. The before move walk uses the working **All inputs** path: navigate, select moving, open comparison, load profile, select All inputs, open monthly costs, include the saved goal, compare. Exact traces and figures are in the [before JSON](validation/streamlined-2026-11-17/before-audit.json) and [after JSON](validation/streamlined-2026-11-17/after-audit.json).

The goal already had an immediate answer and the purchase already took two desktop control clicks. Their gains are fewer comparison routes and competing controls. Guest purchase asks less because its answer is explicitly limited to cash today; it no longer requires monthly totals before giving that answer.

## Same fictional figures, same financial meaning

Monthly pay $2,400; rent $1,500; other regular costs $500; dining $300; checking $2,500. Emergency fund: $3,620 saved, $5,000 target, six months, $100/month, 0% interest.

- **Goal:** $4,220 projected, $780 short. The model verifies a $130/month dining reduction and $230/month goal contribution: $5,000 at the deadline with $0 left each month. Testing does not alter the original $300 dining or $100 contribution.
- **Purchase:** a $200 purchase leaves $2,300 cash. The existing $780 goal gap remains; monthly money remains $0.
- **Move:** $1,700 new rent, $150 extra monthly costs and $1,200 upfront (the before form split this into $1,000 deposit + $200 moving) leaves $1,300 cash, a $250 monthly shortfall and a $1,380 goal gap. The verified alternative is a **$1,350/month rent budget**, keeping the same upfront amount and the existing goal projection. It is a budget to test, not an advertised rental offer.

The move solver retains debts, transfers and other goals. Negative cost adjustments require a recorded expense and cannot exceed it. Cash pays upfront/purchase costs; neither borrowing nor goal withdrawals are assumed. Unknown amounts remain distinct from confirmed zero. A cash cushion warning remains beside a result when the user has selected one. Saved goal projections show their recorded date and an overdue selected deadline is surfaced.

## Verification and screenshots

[Before/after desktop and mobile gallery](validation/streamlined-2026-11-17/README.md). Captures are unedited browser screenshots; JSON includes measured actions and routes.

Run `python -m pytest -q` for the calculation and Streamlit suite. Browser coverage is `tests/browser_smoke.py`, `tests/result_first_browser.py` and `tests/journey_audit.py` (Playwright Chromium). The matched audit exports the workspace before and after testing and checks identical saved blocks, exercises Back with retained purchase/move entries, tests the modeled move alternative, and covers desktop/mobile layout. The result-first suite covers rescued and on-track goals, a modeled later deadline, missing income, stale figures, explicit approval and exported applied changes. The broader suite retains optional tools, workspace restore and single-user persistence/deletion coverage.

**Local validation:** 534 Python tests passed; all 12 broader desktop/mobile browser journeys and all 10 result-first journeys passed, including a new-session persistence/deletion check. The matched before/after audit adds eight walkthroughs per version, with the source-preservation and explicit-apply assertions described above. Screenshots are in the [gallery](validation/streamlined-2026-11-17/README.md).

To reproduce the counts, start each version on a separate local port, then run:

```sh
MONEYLAB_TEST_URL=http://127.0.0.1:8550 python tests/journey_audit.py --mode before --output artifacts/before
MONEYLAB_TEST_URL=http://127.0.0.1:8554 python tests/journey_audit.py --mode after --output artifacts/after
```
