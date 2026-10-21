# MoneyLab — Application Development Project

**Phase 1 submission — October 27, 2026, 5 PM**

## Problem and purpose

Many individuals need a straightforward way to see the impact of everyday financial decisions. Budget worksheets can show current spending, but they do not always make it easy to see how monthly surplus, loan interest, and scheduled repayments interact over time. MoneyLab addresses that problem with a Python application that projects a user's financial position from a small set of editable inputs.

The application is **general-purpose** and is intended for students, recent graduates, early-career professionals, and other people interested in personal financial planning. The sample data is fictional; users are not asked to connect financial accounts or provide personal information to an external service.

## Current application and features

MoneyLab currently implements these working application features:

1. **Financial profile inputs:** Starting cash savings, monthly take-home income, living expenses, one loan's balance, nominal annual interest rate (percent), scheduled monthly loan payment, and projection horizon from 1 to 600 months.
2. **Cash-flow analysis:** Monthly income minus living expenses and actual loan payment; living expenses are intentionally separate from debt payments.
3. **Loan repayment model:** Interest is calculated monthly, payments go to interest before principal, and final payments are capped to the remaining amount due. The model tracks negative amortization, cumulative interest, and the modeled payoff month when applicable.
4. **Financial projections:** Month-by-month savings, loan balance, unmet cash needs (unfunded shortfalls), and modeled partial net position. Projections include Month 0 and a summary.
5. **Streamlit dashboard:** Input form, metrics, charts, month-by-month table, warnings, and approximate calendar payoff month.
6. **Strategy comparison (early extension):** Side-by-side simulation of saving all surplus versus allocating an optional part of the available surplus to additional loan repayment, holding all other assumptions constant.
7. **Exports:** Download exact-cent results as CSV for individual or both strategies.

## Design and implementation

The central financial functions live in `moneylab/engine.py` and are **independent of Streamlit**. The comparison logic lives in `moneylab/strategies.py`, and CSV reporting lives in `moneylab/reporting.py`. The interface is in `app.py`. `Decimal` and explicit cent rounding are used for monetary calculations. `pytest` tests cover cash-flow arithmetic, input validation, loan amortization, longitudinal accounting identities, edge cases, strategy comparisons, and exports.

This separation allows the same financial engine to run in the Streamlit interface, from automated tests, or from a Colab notebook.

## Major decisions, limitations, and compromises

- Initial development concentrates on **one loan**, not a full multi-account budgeting system.
- Income, living expenses, loan rate, and scheduled payments are constant within one simulation.
- Savings do not earn interest; investments, inflation, taxes beyond take-home pay, fees, and other assets/liabilities are not included.
- Unpaid interest is added to the modeled loan balance each month; capitalization terms differ among real loan products.
- The model assumes contractual payments occur, even if cash is insufficient. The shortfall is shown as an **unfunded planning amount** rather than silently borrowing money.
- Extra payments are only made from current monthly surplus after covering any earlier shortfall, and are capped at the remaining loan balance. Existing cash savings are not drawn down.
- The reported financial position is a **partial net position**, not the person's complete net worth.
- Calculations are educational projections, not predictions or financial advice.

The advantage of this limited scope is a reliable application that is feasible to test and demonstrate by the course deadlines.

## Code and demonstrations

- **GitHub repository:** https://github.com/jbj-02/moneylab
- **Main application:** `app.py`
- **Core code:** `moneylab/engine.py`
- **Browser-based Python notebook:** https://colab.research.google.com/github/jbj-02/moneylab/blob/main/notebooks/phase1_demo.ipynb
- **Automated tests:** `tests/`

The notebook uses the source hosted on GitHub and demonstrates the exact engine used by the Streamlit dashboard. To meet the professor's requirement for a **shared Colab notebook**, open the notebook in Colab, save a copy to Google Drive, and configure sharing according to the professor's access instructions. Providing only a GitHub link should not be assumed to satisfy the sharing requirement.

## How to run the application

From the repository root in Python 3.12+:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -v
python -m streamlit run app.py
```

The app opens in a local browser. Edit the sidebar numbers and press **Recalculate**. The Overview tab shows cash flow and the baseline projection. Compare strategies shows the saving-versus-extra-debt comparison. Monthly data & export provides a downloadable CSV. Assumptions explains the calculation boundaries.

## Planned follow-up work

For Phase 2, refine the strategy comparison based on feedback and document implementation challenges. For Phase 3, validate the app in a clean environment, write full user instructions, record a demonstration, and consider modest Version 2 improvements such as multiple loans, investment returns, or one-time expense shocks.

**Phase 1 reminder:** Ensure this written description and the specifically required shared notebook or approved alternative are submitted before 5 PM on October 27, 2026.
