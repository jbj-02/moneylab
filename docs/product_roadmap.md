# MoneyLab — Learning, confidence and decision support roadmap

## One-sentence product promise

**Understand your money. Enjoy your life.** MoneyLab helps people in their
first years of financial independence build a personal financial profile,
learn in context and explore tradeoffs without shame or mystery.

## Why use it rather than a spreadsheet?

A spreadsheet can add up a budget. MoneyLab's intended value is the
**guided experience** around those numbers:

1. **Get started without being a financial expert.** Start from zero and
   choose a common life situation (first paycheck, moving out, saving,
   investing, managing student debt or organizing a financial check-up).
   Add only the building blocks that apply to you.
2. **Understand rather than just track.** Short, contextual lessons explain
   take-home pay, monthly buffer, debt, savings, account assumptions,
   retirement, routing, and goals. Optional quiz feedback supports learning.
3. **Know what the entered plan does and does not tell you.** The MoneyLab
   Check-In explains insufficient information, possible financial issues,
   goals and available financial flexibility. It does **not** pretend that
   manually entered numbers are verified or continuously current.
4. **Try decisions safely.** The What-if Lab compares calculated outcomes
   before the user makes a real financial commitment.

## Current experience (implemented)

- Empty-first workspace plus optional fictional profile
- Life-situation guided first-block suggestions, never mandatory
- Editable financial blocks, account types, recurring costs, debt and income routing
- Transparent Decimal-based monthly projections and what-if impact alerts
- **MoneyLab Check-In**:
  - needs attention / not enough information / on track *in the entered model*
  - explicit user review confirmation tied to the current profile contents
  - obligations, goal status, loan growth and modeled unfunded shortfalls
  - months of **recorded spending** covered by entered checking/cash and
    liquid savings balances; retirement, brokerage, CDs, HSA and earmarked
    goal balances are intentionally not used
  - recommended next actions, not a black-box score
- **Learn by doing**:
  - short lessons selected from current financial blocks
  - interactive self-check questions with helpful explanations
  - lesson progress tracked only in the active Streamlit session
- JSON profile download/import and CSV financial projections
- Original Classic Simulator and existing Colab notebook remain available

## Safety and trust requirements

- An **on-track** label must require an explicitly reviewed set of income,
  expense and cash blocks, no flagged affordability/debt problems within the
  selected horizon, and no missed or unassessed goals.
- Always say when critical inputs are missing or a projection cannot cover
  a goal deadline. An unreviewed model cannot promise peace of mind.
- Figures are estimates from **manual input**, not live account balances.
  Loan terms, tax rules, actual investment returns and spending timing can vary.
- Roth, 401(k), HSA and brokerage balances are not extra weekly spending cash.
- Financial insights should show an explanation and practical next action,
  never shame users for spending or give an unexplained numerical health score.
- Consent-based Plaid data connections are explicitly post-course and
  should not be a prerequisite for core functionality.

## Next improvements: staged development plan

### Stage A — Ease of use and trust
- In-place editing immediately after adding a suggested template
- Explain which inputs each check-in status depends on
- Explicit profile update/review date if persistent storage is introduced
- Better mobile-size navigation and WCAG accessibility checks
- Test with real students using synthetic or self-selected example figures

### Stage B — Truly useful weekly check-ins
- Optional profile history **with explicit opt-in**, versioned snapshots
- Frequency selection and a low-friction "what changed?" update flow
- Calendar-aware paychecks, bill due dates and recurring irregular expenses
- Short-term cash-buffer calculation based on actual timing instead of
  monthly averages, carefully labeled when dates are unknown
- User-controlled notifications only after actual scheduling and consent

### Stage C — Decision coaching
- Named What-if Lab scenarios and multi-variable changes
- More actionable goal-shortfall explanations, with transparent math
- One-time costs (moving, repairs, car purchase)
- Educational simulations for debt payoff and liquidity tradeoffs
- Accessible "why?" explanations linking from each warning to relevant lessons

### Much later, optional
- Native iOS application backed by tested Python financial APIs
- Bank CSV import with explicit user permission and secure processing
- Account persistence with privacy controls, data deletion and authentication
- Plaid consent-based synchronization only after privacy/security review

## How to evaluate whether people would download it

Recruit 10–20 college seniors or recent graduates. Use hypothetical
financial data if needed. Measure:

- **Onboarding:** Can participants make a useful profile without prior training?
- **Comprehension:** Can they explain the meaning of their spending-buffer
  estimate and its limits?
- **Decision quality:** Can they compare two apartments or car-payment
  scenarios and explain the tradeoff?
- **Confidence with calibration:** Do users feel clearer about their next
  action *without* assuming that hypothetical results are guaranteed?
- **Return value:** Would they want to review the check-in after a real change
  to income, rent or goals?

A successful educational financial app should improve comprehension and
decision confidence, not inflate engagement through anxiety-driven alerts.
