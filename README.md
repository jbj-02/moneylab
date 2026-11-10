# MoneyLab

MoneyLab helps students, recent graduates and early-career professionals turn their recorded finances into a practical plan. Choose a goal, see the saving pace your budget can support, and compare a decision before changing your plan. Python financial services power the current Streamlit interface; the frontend is a replaceable product choice.

[Open MoneyLab](https://moneylab-dev.streamlit.app/) · [Project documentation](docs/README.md)

[![Python checks](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml/badge.svg)](https://github.com/jbj-02/moneylab/actions/workflows/tests.yml)

## Build a plan

- **Start with a priority.** One setup flow asks what matters, your monthly money, then balances and debts. Blank answers remain unknown. The portion of savings assigned to a goal is counted once.
- **Know your next step.** My Plan explains why an action comes first, where its money would come from, and what it changes elsewhere. Edit your priority and compare a current pace, increased saving, a later date, a smaller target or an expense reduction you select.
- **Compare before committing.** Test purchases, recurring costs, recorded expenses, income, loan payments or a move. See cash, debt, interest and goal effects. Inspect the exact edits and explicitly approve any plan update; exploring is temporary.
- **Test uncertainty and follow through.** Stress the same income, expense or one-time-cost assumption against both plans. After approval, see the chosen contribution, target and projected date; compare a new recorded balance with that schedule before updating it.
- **Return to your figures.** My Finances edits the shared profile. Backups and the opt-in single-user local store preserve your selected schedule and preference. Public account-based saving remains deferred.

### Example

An emergency fund has $8,000 saved, a $10,000 target six months away, and $200/month planned. The model shows an $800 deadline gap and tests $333.34/month as an alternative. If recorded commitments leave only $200/month available, it reports that the deadline cannot be funded; you can compare a later date or a reduction you choose to a recorded expense.

Projections use monthly averages, constant entered rates and the balances you record. They do not infer borrowing, new income, taxes or daily bill timing. Separate recommendations may use the same available money and must be compared one at a time.

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

Run the automated suite with `python -m pytest -q`. GitHub Actions also runs desktop and mobile Chromium journeys on pull requests. See the [action-plan notes](docs/action-plan.md) for calculations, dates and validation, and the [overhaul notes](docs/product-overhaul.md) for local-saving setup and hosted persistence requirements.

## Repository layout

| Path | Contents |
| --- | --- |
| `app.py`, `pages/` | Streamlit navigation and page entry points |
| `moneylab/` | Calculation engines, decision and profile logic, UI, and workspace handling |
| `tests/` | Calculation regressions, Streamlit tests, and browser smoke checks |
| [`docs/`](docs/README.md) | Product and technical documentation, course submission, and release archive |
| [`notebooks/`](notebooks/) | Phase 1 Python demo |

## Data and setup

MoneyLab uses entered figures and has no bank connection. Public deployments are session-only and disclose that status. For single-user development, `MONEYLAB_LOCAL_STORE` enables private-file SQLite saving only with a loopback server address. This is plaintext local storage, without account authentication, and must not be publicly exposed. Workspace versions 1–4 import into version 5; exports also preserve unknowns, example-data labels, preferences and the selected schedule. The optional decision parser runs locally without an AI API key. Private feedback delivery requires the owner's Formspree endpoint.

[Phase 1 submission](docs/phase1_submission.md) · [Phase 1 Colab demo](https://colab.research.google.com/github/jbj-02/moneylab/blob/main/notebooks/phase1_demo.ipynb)

All rights reserved. The project currently has no open-source license.
