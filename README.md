# 💰 MoneyLab

**Personal Financial Planning & Decision Simulator** — a general-purpose Python and Streamlit application that helps you model future cash savings, loan repayments, and the consequences of allocating your monthly surplus.

[![Python checks](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml/badge.svg)](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml)

## What it does

- **Your financial profile:** Enter current savings, monthly take-home income, living expenses, outstanding loan balance, annual loan rate, monthly payment, and projection length.
- **Monthly cash flow:** See income minus living expenses and actual loan payments, without double-counting.
- **Loan amortization:** Model monthly interest, principal, loan balances, early payoff, and negative amortization.
- **Financial outlook:** Explore monthly savings, remaining debt, cash shortfalls, and modeled partial net financial position.
- **Strategy comparisons:** Compare saving monthly surplus against applying an optional extra amount toward loan repayment. Both strategies use the same baseline financial assumptions. Extra payments are capped to affordability.
- **Interactive dashboard:** View summaries, charts, estimated payoff month, warnings, and a full monthly breakdown.
- **CSV downloads:** Export a projection or both scenarios with exact cent values.

The application operates **without a bank connection, paid API, or login**. Sample values are fictional.

## Local installation

Python 3.12+ recommended.

```powershell
git clone https://github.com/jbj-02/moneylab.git
cd moneylab
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On macOS/Linux use `python3 -m venv .venv` and `source .venv/bin/activate`.

In your browser, change values in the sidebar and select **Recalculate**. Explore four tabs:

1. **Overview:** baseline financial position, monthly cash flow, and projections.
2. **Compare strategies:** save your surplus versus add an affordable extra loan payment.
3. **Monthly data & export:** inspect and download your results.
4. **Assumptions:** understand exactly what the model includes or excludes.

## Run automated tests

```powershell
python -m pytest -v
```

Tests check financial arithmetic, loan payoff, negative amortization, input validation, strategy fairness, CSV reporting, and dashboard rendering. GitHub Actions runs the suite on pushes to `main` and pull requests.

## Project layout

```text
moneylab/
├── app.py                  # Streamlit user interface
├── moneylab/
│   ├── __init__.py
│   ├── engine.py           # Pure Python financial projections
│   ├── strategies.py       # Comparable financial strategies
│   └── reporting.py        # Exact-cent CSV exports
├── tests/                  # Unit and Streamlit interface tests
├── notebooks/
│   └── phase1_demo.ipynb   # Colab-compatible demonstration
├── docs/
│   └── phase1_submission.md
├── requirements.txt
└── README.md
```

## University assignment submission

- [Phase 1 written description](docs/phase1_submission.md)
- [Colab-compatible Python demonstration notebook](notebooks/phase1_demo.ipynb)
- [Open demonstration in Colab](https://colab.research.google.com/github/jbj-02/moneylab/blob/main/notebooks/phase1_demo.ipynb)

The course requires a shared Colab notebook during Phases 1 and 2. The notebook uses this repository's calculation engine, but **the repository owner must save/share an appropriate Colab copy and confirm the professor's access**. Do not assume the public GitHub link alone satisfies the professor's instructions.

## Assumptions and limitations

- Amounts are in USD. Currency calculations use Python `Decimal` rounded to cents.
- Income, expenses, and loan interest rates remain constant across each projection.
- Loan interest accrues monthly on opening principal at the nominal annual percentage rate divided by 12.
- Payments pay interest before principal. Final payments are capped to the amount actually owed.
- When a payment fails to cover interest, the model **adds unpaid interest to the loan balance monthly**. Actual loan contracts vary.
- Mandatory payments are assumed to occur even when cash is insufficient; deficits are shown as **unfunded shortfalls** rather than invented bank overdrafts or new loans.
- Optional extra payments come only from available monthly surplus after earlier shortfalls are covered. They never consume starting cash savings.
- Savings do not accrue interest. Investments, inflation, variable cash flows, multiple loans, asset values, and extra real-world financial obligations are not included.
- **Modeled net position = cash savings − modeled loan debt − unfunded shortfall.** It is not complete net worth.

**MoneyLab is a mathematical scenario simulator for education and planning, not a prediction of financial outcomes or personalized advice.**

## Roadmap

**Available in Version 1:** Cash flow, amortization, financial projection, two-strategy comparison, interactive graphs, approximate payoff month, monthly exports.

**Possible Version 2 additions:** Multiple loans, cash yield and investments, profile saving/loading, variable cash flow, one-time expense shocks, and deployment. These are not required to run Version 1.

## License

No license selected yet. All rights reserved unless a license is later added.
