# MoneyLab

MoneyLab is a Python and Streamlit decision simulator for students, recent graduates, and anyone working toward financial independence. Use it to see what a move or a new expense would cost and how changing your plan could affect your goals.

[Open MoneyLab](https://moneylab-dev.streamlit.app/) · [Project documentation](docs/README.md)

[![Python checks](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml/badge.svg)](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml)

## Try a decision

- **Moving out.** Start with a fictional example, your own numbers, or your My Money profile. Enter your current situation and proposed costs, then review them before calculating. Back and Continue retain your entries. All inputs is available for a single form.
- **Move timing.** Set a monthly savings amount, a target month, and the cash you want left after moving. Compare waiting, redirecting part of a recorded expense, or choosing a lower rent share and different move-in costs. Compare the timing, cash after the move, and monthly remainder with your current plan.
- **Purchases and recurring expenses.** Compare a proposed cost with your monthly budget and cash. You can also start by describing a decision in plain English and reviewing the amounts MoneyLab extracted.
- **My Money and Goals.** Build a profile from income, expenses, loans, accounts, and savings goals. Start empty, add blocks as needed, or use Quick Start. Save and restore your profile and supported scenario drafts with a workspace JSON file.

### Example

If your move-in costs and cash cushion leave a gap of $1,200, saving $200 a month closes it in six months. Cutting a recorded expense by $100 a month and saving that difference brings it down to four months, assuming your budget has room for the transfer.

The move estimate uses whole months, a fixed savings pace, and the balances and expenses you enter. Cash that you have not allowed for upfront costs can count toward your cushion if it remains accessible after the move. The planner shows a monthly shortfall separately from the upfront target. Move timing comparisons are temporary.

## Run locally

Use Python 3.12 or newer.

```sh
git clone https://github.com/jbj-02/moneylab.git
cd moneylab
python -m venv .venv
```

Activate the environment with `source .venv/bin/activate` on macOS/Linux or `.\.venv\Scripts\Activate.ps1` in PowerShell. Then run:

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Run the automated suite with `python -m pytest -q`. GitHub Actions also runs desktop and mobile browser smoke tests on pull requests.

## Repository layout

| Path | Contents |
| --- | --- |
| `app.py`, `pages/` | Streamlit navigation and page entry points |
| `moneylab/` | Calculation engines, decision and profile logic, UI, and workspace handling |
| `tests/` | Calculation regressions, Streamlit tests, and browser smoke checks |
| [`docs/`](docs/README.md) | Product and technical documentation, course submission, and release archive |
| [`notebooks/`](notebooks/) | Phase 1 Python demo |

## Data and setup

MoneyLab uses figures entered by the user and has no bank connection. Work stays in the Streamlit session until you explicitly export it. The built-in text parser runs without an AI API key. The [optional Quick Start cloud AI feature](docs/cloud_setup.md) requires owner configuration and user consent. Private feedback delivery requires the owner's Formspree endpoint. Setup details are in the [workflow release notes](docs/archive/workflow_release.md).

[Phase 1 submission](docs/phase1_submission.md) · [Phase 1 Colab demo](https://colab.research.google.com/github/jbj-02/moneylab/blob/main/notebooks/phase1_demo.ipynb)

All rights reserved. The project currently has no open-source license.
