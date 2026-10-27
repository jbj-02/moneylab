# 💰 MoneyLab

**Understand your money. Enjoy your life.** MoneyLab is a personalized financial learning and planning app for the transition to financial independence. It combines educational guidance, a careful MoneyLab Check-In, budgeting building blocks, and what-if decisions.

[![Python checks](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml/badge.svg)](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml)

## Try the new experience

**UX Refresh:** The app now has **five primary destinations: Home, My Money, Goals, Explore, and Learn**. Native Streamlit navigation replaces the seven-section radio menu. **Settings & data** and the original **Classic Simulator** remain accessible as secondary sidebar links. New workspaces start empty. Choose a situation on Home or add a suggested block; example values are fictional and should be edited.

The modular profile is built from independent **financial building blocks**:

| Block | Example | Input |
| --- | --- | --- |
| Income | Take-home salary, side job | Monthly income |
| Expense | Rent, groceries, entertainment, subscriptions | Monthly spending |
| Loan | Student loan, car financing | Balance, APR, required payment |
| Cash | Checking account | Starting balance |
| High-yield savings (HYSA) | Emergency fund | Balance, hypothetical annual yield, planned contribution |
| Roth IRA | Retirement account | Balance, hypothetical annual growth, planned contribution |
| Dedicated savings goal | Trip, moving fund | Balance, contribution, target, months to goal |

On **My Money**, blocks are grouped into readable cards for Income, Everyday spending, Accounts & savings, Loans & debt, and Savings goals. A single Add action opens a focused editor; each card has Edit and a More options menu for reordering or confirming deletion. Paycheck routing is available under an Advanced expander. The expanded library includes traditional and Roth IRAs, 401(k) variants, 403(b), money market and CD accounts, brokerage, HSA, 529 and traditional savings. All are simplified balances with hypothetical fixed rates; MoneyLab does not yet implement account-specific tax rules, employer contributions, spending restrictions or deposit maturity schedules. Multiple loans are supported. A **classic loan simulator** remains accessible through the sidebar for the Phase 1 calculations and comparison features.

### What the new dashboard answers

- **Where does my monthly income go?** Under **My Money → Advanced · Route take-home income into accounts**, route net income to checking, savings, retirement or investment blocks using fixed dollar amounts or percentages. The engine avoids double-counting routed deposits as income or spending.
- **How much flexibility does the plan show?** Home emphasizes one careful check-in status, income, recorded commitments, and *additional monthly flexibility*. A reassuring amount appears only if reviewed inputs yield an on-track modeled plan; it is **not verified bank money**.
- **How might my position change?** Expand **Home → Explore your detailed financial projection** for modeled cash, accounts, debt and net position.
- **What happens if rent changes?** The **Explore** page leads with three significant before-and-after results and the most important explanatory effects. Full impact details and charts are optional expanders. Save up to 20 named expense-change scenarios without changing your baseline.
- **Will I reach my savings goal?** The dedicated **Goals** page creates and edits the same underlying goal blocks used elsewhere. It displays current savings, target, and the projected result at each goal's deadline—even if the dashboard uses a shorter projection horizon.
- **Can I keep my setup?** Open the secondary **Settings & data** page to export or restore profile and scenario JSON (including legacy version 1 imports), or download a projection CSV.
- **What should I check this week?** **Home** shows the most useful check-in finding. Expand **Update your finances and upcoming dates** to refresh a balance or recurring expense, review recorded inputs, and inspect manually entered upcoming paydays or bills.
- **Can I learn while using the app?** The **Learn** tab offers short lessons matched to the blocks the user adds, such as net pay, HYSA assumptions, loan interest and retirement accounts, with optional quick self-check quizzes.

The old simulation remains available at `pages/2_Classic_Simulator.py`.

## Install and run

Use Python 3.12 or newer.

```powershell
git clone https://github.com/jbj-02/moneylab.git
cd moneylab
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

To update an existing checkout:

```powershell
git pull origin main
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

macOS/Linux: use `python3 -m venv .venv` and `source .venv/bin/activate`.

### Tests

```powershell
python -m pytest -v
```

GitHub Actions runs tests on pushes and pull requests. Legacy cash-flow, amortization, and scenario test suites are retained; modular-block tests cover financial invariants, affordability, goals, editable profiles and JSON imports.

## Source structure

- `app.py` — minimal native Streamlit multipage router and shared sidebar controls.
- `moneylab/ui_app.py` — five focused page renderers, card-based block management and focused add/edit dialogs.
- `pages/0_Home.py`, `pages/1_My_Money.py`, `pages/2_Goals.py`, `pages/3_Explore.py`, `pages/4_Learn.py` — primary page entrypoints.
- `pages/6_Settings.py` — secondary workspace import/export page.
- `pages/2_Classic_Simulator.py` — original one-loan Streamlit interface, preserved.
- `moneylab/blocks.py` — validation, multiple-block projection, what-if changes, JSON profiles.
- `moneylab/engine.py` — original pure-Python cash-flow and loan calculation engine.
- `moneylab/strategies.py` — original extra-payment comparisons.
- `moneylab/reporting.py` — original CSV reports.
- `moneylab/checkin.py` — conservative, explainable check-in from financial projection results.
- `moneylab/cadence.py` — weekly/biweekly/monthly/yearly conversion and upcoming-payday/bill calendar utilities.
- `moneylab/workspace.py` — versioned profile and saved scenario JSON storage.
- `moneylab/learning.py` — contextual mini-lessons and self-check feedback.
- `moneylab/insights.py` — what-if impact descriptions.
- `moneylab/presets.py` — one-click suggested financial blocks.
- `tests/` — regression tests and Streamlit smoke tests.
- `notebooks/phase1_demo.ipynb` — Colab demonstration of the original engine.
- `docs/phase1_submission.md` — Phase 1 write-up.
- `docs/product_roadmap.md` — learning-first product strategy, privacy safeguards and next phases.

## Routing example (manual-first)

1. Add an **Income** block with monthly take-home salary, e.g. $4,000.
2. Add a **Checking account** block and any other destination accounts (e.g. HYSA, Roth IRA).
3. In **My Money → Advanced · Route take-home income into accounts**, choose the paycheck and make allocations. Fixed-dollar and percentage routes are supported.
4. MoneyLab validates that routed amounts do not exceed that income and keeps any unrouted remainder in modeled cash. Existing separate monthly contributions to savings accounts are funded only from cash left after expenses, loan payments, and prior shortfalls.
5. Check **Home** for the financial summary and **Explore** to test how a changing expense affects your projections. MoneyLab currently models routing destinations but pools checking for the cash-flow projection.

**Important:** Multiple checking blocks may be named as routing destinations, but the current model **pools cash for the financial projection**; it does not yet maintain independent checking account transaction ledgers. Treat the weekly spending number as an educational planning estimate, not verified account funds.

## Scheduling and planning assumptions

Choose weekly, **every two weeks**, monthly or yearly amounts when adding or editing an income/expense block. The monthly simulator converts to a mathematical monthly average: weekly × 52 ÷ 12, biweekly × 26 ÷ 12, monthly as entered, and yearly ÷ 12. It uses `Decimal` and rounds to cents for consistent model arithmetic. **Averaged income and bills are not actual cash arrivals or withdrawals on particular dates.** For example, a yearly $1,200 insurance bill becomes a $100 monthly *planning equivalent*; it is still one real-world yearly bill.

Optionally specify the **next expected payday or bill date** in the focused block editor. Home's review expander shows expected upcoming events, but the calendar does **not** simulate individual account balances on those dates or send reminders. Month-end occurrences clip to shorter months. The calendar is informational and must not be used as a guarantee that sufficient money will be available when a bill is due.

Saved What-if scenarios currently change one expense's *monthly equivalent*. They are compared with the current profile and stored in your Streamlit session. Export a **MoneyLab workspace (JSON)** to preserve both the profile and named scenarios. Older profile-only JSON files are compatible with imports. Saving a scenario does not apply it to the original profile.

## Financial modeling and privacy limitations

**This is an educational planning prototype, not a bank balance, financial forecast or personal financial advice.**

- The current version is **manual-first**. There is no Plaid connection, automatic transaction feed or financial login. **Check-ins only evaluate manually entered financial data.** An on-track status is not an assurance of financial health or accuracy and requires an explicit user review of the current profile. Balances and estimates can become stale.
- Data is held in the current Streamlit session and **is not automatically saved to an account**. Export your profile JSON to save it; do not enter information you would not want processed by the application host.
- Income, expenses, scheduled payments, and annual rate assumptions remain constant through the projection.
- Money and loan interest are calculated using `Decimal` cents; monthly interest is APR/12 on each loan's opening balance. Unpaid loan interest is capitalized monthly; actual contracts vary.
- Direct deposits from **take-home** pay can be routed to cash and investment/savings blocks. Unallocated income remains in modeled cash. Subsequent recurring contributions from cash occur only from **affordable monthly surplus**; neither deposits nor transfers are double-counted as expenses. Withholding before take-home pay, tax treatment, payroll deductions and employer retirement matches are not modeled. The app tracks shortfalls rather than silently inventing a new loan.
- HYSA yields and Roth IRA growth are **deterministic hypothetical assumptions**, not quotes or guarantees. Retirement contribution limits, eligibility, taxes, investment volatility, inflation and withdrawal restrictions are **not modeled**.
- The extra weekly spending estimate equals available *first-month unallocated funds* × 12/52 after entered expenses, payments and affordable transfers; it omits costs the user has not entered and does not represent spendable retirement funds.
- Net position includes only the modeled cash, loan balances and other included account blocks. This is not a complete statement of net worth.
- Goal blocks each represent a **separate, earmarked account** to prevent counting one savings balance toward multiple goals automatically.

## Roadmap

**Now:** UX Refresh with five native pages, concise Home check-in, readable grouped financial-block cards with focused editing, integrated goal creation and deadline projections, streamlined Explain/Explore impact summaries, and secondary Settings; alongside empty-first onboarding, recurring amounts, optional dates, lessons, routing, scenarios, and JSON/CSV exports.

**Next (course milestones):** User testing with recent graduates; further mobile-size layout and accessibility improvements; goal priority settings; recurring expense exceptions; and a true date-based short-term account cash ledger. Scheduled notifications, history and persistent logins would require separate consent, security and storage design.

**Later (post-course):** Optional secure profile accounts and mobile apps, transaction CSV imports, and economic context APIs.

**Much later, optional:** Plaid integration for consent-based bank transaction syncing. It would require rigorous privacy/security review and is *not* a dependency of MoneyLab's core value.

## Academic demo

- [Phase 1 description](docs/phase1_submission.md)
- [Google Colab notebook](https://colab.research.google.com/github/jbj-02/moneylab/blob/main/notebooks/phase1_demo.ipynb)

The Colab notebook demonstrates the original calculation engine, while the modular user interface is the next development stage.

## License

No license chosen. All rights reserved unless added later.
