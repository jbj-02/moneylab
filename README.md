# 💰 MoneyLab

**A personalized financial planning and decision simulator for life after college.** MoneyLab helps people understand their monthly obligations, decide what they can afford, and explore how their choices affect savings and financial flexibility.

[![Python checks](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml/badge.svg)](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml)

## Try the new experience

Open the Streamlit app and choose **My dashboard**, **Build my profile**, **What-if Lab**, **Goals & insights**, or **Export / import**. **New profiles start completely empty**: add only the blocks relevant to you, or deliberately load the optional fictional example from the sidebar.

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

Blocks can be added, renamed, edited, removed, and reordered. The expanded library includes traditional and Roth IRAs, 401(k) variants, 403(b), money market and CD accounts, brokerage, HSA, 529 and traditional savings. All are simplified balances with hypothetical fixed rates; MoneyLab does not yet implement account-specific tax rules, employer contributions, spending restrictions or deposit maturity schedules. Multiple loans are supported. A **classic loan simulator** remains accessible through the sidebar for the Phase 1 calculations and comparison features.

### What the new dashboard answers

- **Where does my monthly income go?** Route take-home income from each paycheck to checking, savings, retirement or investment account blocks using **fixed dollar amounts or percentages**. Remaining income stays in modeled cash. Routed deposits are not counted as new income or spending. See routing destinations on the dashboard.
- **What can I spend beyond my existing budget?** See an *estimated extra weekly spend* figure calculated from the unallocated first-month buffer. It is a planning estimate, **not verified bank money**.
- **How might my position change?** View projected cash, other assets, loan balances and modeled net position.
- **What happens if rent changes?** Adjust an expense in the What-if Lab. MoneyLab calculates the separate scenario and presents **specific impact alerts** for spending flexibility, cash, accounts, debt, goals and final modeled financial position, without modifying your profile.
- **Will I reach my savings goal?** Dedicated goal blocks compare the projected earmarked balance with the target at its deadline.
- **Can I keep my setup?** Export a profile to JSON and import it later; download month-by-month results as CSV.

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

- `app.py` — personalized Streamlit home and editable blocks.
- `pages/2_Classic_Simulator.py` — original one-loan Streamlit interface, preserved.
- `moneylab/blocks.py` — validation, multiple-block projection, what-if changes, JSON profiles.
- `moneylab/engine.py` — original pure-Python cash-flow and loan calculation engine.
- `moneylab/strategies.py` — original extra-payment comparisons.
- `moneylab/reporting.py` — original CSV reports.
- `tests/` — regression tests and Streamlit smoke tests.
- `notebooks/phase1_demo.ipynb` — Colab demonstration of the original engine.
- `docs/phase1_submission.md` — Phase 1 write-up.

## Routing example (manual-first)

1. Add an **Income** block with monthly take-home salary, e.g. $4,000.
2. Add a **Checking account** block and any other destination accounts (e.g. HYSA, Roth IRA).
3. In **Build my profile → Income routing**, choose the paycheck, then create allocations: $3,500 to checking, $300 to HYSA, and $200 to Roth IRA. Fixed-dollar and percentage routes are supported.
4. MoneyLab validates that routed amounts do not exceed that income and keeps any unrouted remainder in modeled cash. Existing separate monthly contributions to savings accounts are funded only from cash left after expenses, loan payments, and prior shortfalls.
5. In **My dashboard**, review monthly deposit destinations. In **What-if Lab**, adjust an expense and read the projected impact alerts.

**Important:** Multiple checking blocks may be named as routing destinations, but the current model **pools cash for the financial projection**; it does not yet maintain independent checking account transaction ledgers. Treat the weekly spending number as an educational planning estimate, not verified account funds.

## Financial modeling and privacy limitations

**This is an educational planning prototype, not a bank balance, financial forecast or personal financial advice.**

- The current version is **manual-first**. There is no Plaid connection, automatic transaction feed or financial login.
- Data is held in the current Streamlit session and **is not automatically saved to an account**. Export your profile JSON to save it; do not enter information you would not want processed by the application host.
- Income, expenses, scheduled payments, and annual rate assumptions remain constant through the projection.
- Money and loan interest are calculated using `Decimal` cents; monthly interest is APR/12 on each loan's opening balance. Unpaid loan interest is capitalized monthly; actual contracts vary.
- Direct deposits from **take-home** pay can be routed to cash and investment/savings blocks. Unallocated income remains in modeled cash. Subsequent recurring contributions from cash occur only from **affordable monthly surplus**; neither deposits nor transfers are double-counted as expenses. Withholding before take-home pay, tax treatment, payroll deductions and employer retirement matches are not modeled. The app tracks shortfalls rather than silently inventing a new loan.
- HYSA yields and Roth IRA growth are **deterministic hypothetical assumptions**, not quotes or guarantees. Retirement contribution limits, eligibility, taxes, investment volatility, inflation and withdrawal restrictions are **not modeled**.
- The extra weekly spending estimate equals available *first-month unallocated funds* × 12/52 after entered expenses, payments and affordable transfers; it omits costs the user has not entered and does not represent spendable retirement funds.
- Net position includes only the modeled cash, loan balances and other included account blocks. This is not a complete statement of net worth.
- Goal blocks each represent a **separate, earmarked account** to prevent counting one savings balance toward multiple goals automatically.

## Roadmap

**Now:** Empty-first onboarding; dozens of optional starter blocks; flexible savings/retirement/investment account types; monthly take-home income routing by dollars/percentages; multiple debts, budget categories, goals, what-if impact alerts, spending estimates and JSON/CSV export.

**Next (course milestones):** Add per-checking-account transaction ledgers, saved multi-variable what-if scenarios, improved goal timelines, real pay and bill schedules, mobile-size interface polish and further accessibility tests.

**Later (post-course):** Optional secure profile accounts and mobile apps, transaction CSV imports, and economic context APIs.

**Much later, optional:** Plaid integration for consent-based bank transaction syncing. It would require rigorous privacy/security review and is *not* a dependency of MoneyLab's core value.

## Academic demo

- [Phase 1 description](docs/phase1_submission.md)
- [Google Colab notebook](https://colab.research.google.com/github/jbj-02/moneylab/blob/main/notebooks/phase1_demo.ipynb)

The Colab notebook demonstrates the original calculation engine, while the modular user interface is the next development stage.

## License

No license chosen. All rights reserved unless added later.
