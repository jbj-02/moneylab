# MoneyLab

**MoneyLab** is a Python-based personal financial planning and decision simulator for students, graduates, and anyone who wants to explore simple financial scenarios.

**Current status:** Phase 1 dashboard and projection engine implemented. Strategy comparisons are planned for Phase 2.

## Phase 1 features

- Enter starting cash savings, monthly take-home income, and living expenses **excluding debt payments**.
- Enter one loan's outstanding balance, annual interest rate (as a percent), and required monthly payment.
- Choose a projection horizon from 1 to 600 months.
- Inspect monthly cash flow and loan amortization.
- View projected cash savings, modeled loan debt, and partial net position.
- View a timeline chart and detailed month-by-month calculations.
- See warnings for rising loan balances or unfunded cash shortfalls.

## Quick start

Python 3.12+ recommended. In the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On macOS/Linux, activate with `source .venv/bin/activate` and use
`python3 -m venv .venv` if needed.

The application opens locally in your web browser. No paid service, account connection, or banking data is required. The prefilled inputs are hypothetical examples; edit them to explore other situations.

## Testing

```powershell
python -m pytest -v
```

Unit tests cover input validation, cash flow, monthly loan amortization, and multi-month financial accounting. A Streamlit smoke test checks the initial dashboard against the calculation engine.

## Project structure

- `app.py` — Streamlit presentation and financial profile form.
- `moneylab/engine.py` — pure Python financial calculations, independent of the interface.
- `tests/` — calculation tests and dashboard smoke test.
- `requirements.txt` — dependencies.

## Model assumptions and limitations

- All figures are in US dollars, and dollar arithmetic uses cent rounding.
- Monthly income and living expenses are held constant over the projection.
- Monthly interest is calculated on the starting loan balance using annual nominal interest rate divided by 12, with interest rounded to cents.
- The scheduled payment pays interest first, then principal, and is capped at the balance plus interest owed. Payments stop after payoff.
- Any unpaid interest is added to the modeled loan balance every month; this may not match an actual loan's capitalization terms.
- The model assumes required loan payments occur even when funds are insufficient. Negative modeled cash is tracked as an **unfunded shortfall**, rather than representing a bank overdraft or real borrowing.
- Surpluses first offset unfunded shortfalls; otherwise, they stay as cash savings with no interest. There are no automatic extra loan payments.
- *Modeled net position* = cash savings - modeled loan balance - unfunded shortfall. This is not total net worth because other assets and liabilities are excluded.
- Taxes beyond the supplied take-home income, inflation, investment gains, fees, changing income/expenses, and multiple loans are not modeled.

**MoneyLab is an educational mathematical projection, not a financial prediction or personalized financial advice.**

## Planned enhancements

Phase 2: compare saving surplus versus allocating some of it to additional loan payments, with consistent assumptions and interactive visualizations.

Phase 3: documentation, demonstration, and optional improvements only after the core app is verified.
