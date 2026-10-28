# MoneyLab alpha — decision-first testing guide

**Branch:** `alpha/decision-first-testing` • **Draft PR:** [#1](https://github.com/jbj-02/moneylab/pull/1) • **Target:** do not merge until manual browser/device review.

## Product intent and implementation decisions

**Value proposition:** Make your next money decision with a clearer picture.

The alpha is a financial *decision simulator*, not an account aggregation,
transaction tracker, guaranteed affordability calculator, loan approval system,
or financial adviser. It is designed for students and recent graduates and
does not require a bank account, account signup, cloud AI, or payment.

### What was retained from the first PR

The existing `pages/7_Moving_Out_Alpha.py` route and `moving-alpha` URL
were reused; the untested, inline financial logic was replaced by a thin
page wrapper calling `moneylab/moving_ui.py`. The comparison logic now lives
in the pure, tested `moneylab/moving.py` module and calls the existing
Decimal `project_blocks` engine. No production-branch merge was performed.

### First-time journey

1. Home opens with **What are you trying to figure out?**
2. Choose **Can I afford to move out?** and enter directly, without Quick Start.
3. Select **Try fictional example** to get a safe demonstration, or
   **Enter my own numbers** and provide monthly take-home pay, current
   housing cost, new rent, and whatever other figures are known.
4. Advanced costs, available savings, debt payments and optional goal effects
   are expandable. Unknown optional fields can remain blank; the result
   explicitly identifies them as **missing**, not as confirmed zero expenses.
5. Press **Compare stay vs move**. Results show a plain-English tradeoff,
   current versus proposed monthly costs, before-savings cash margin, upfront
   funding, modeled liquid balances after 6, 12 and 24 months, and goal
   impacts when opted in.
6. Edit inputs and press Compare again. Download a CSV for a *funded*
   comparison, or report feedback through a public GitHub issue template.

Other decision choices allow limited profile-free trials of a new expense or
emergency preparedness. Goals and editing saved expenses still require adding
those blocks through Quick Start/My Money.

## Calculation safeguards

- **Monthly costs:** Current = housing + other living + loan minimums.
  Proposed = rent + utilities + internet + renter's insurance + current
  other living + debt minimums + signed changes to transport, groceries
  and other living expenses. These are separate fields so several
  assumptions can change together.
- **Signed monthly margin:** Monthly take-home pay minus recorded monthly
  costs. Negative values stay negative, never falsely displayed as zero
  available spending money.
- **One-time funds:** Security deposit, moving, furniture and other upfront
  costs are taken from checking/cash first. Savings are used only if the
  user explicitly enables that source. If eligible funds are insufficient,
  the app shows a funding gap and does *not* invent borrowing or project
  an unfunded post-move balance.
- **Liquid comparisons:** Checking/cash plus non-earmarked savings; a
  negative projected cash position represents an unfunded shortfall.
  Goals are calculated and displayed separately.
- **Profile separation:** The comparison never edits `ml_blocks`. Users
  may optionally import *goal blocks only*; existing income, cash, debt
  and other account blocks are not mixed into the manual inputs (which
  would double-count financial information).
- **Timeframes:** 6/12/24 months, using fixed monthly-average expenses
  and the same validated Decimal projection engine.
- **Inputs:** Explicitly validated finite money values with cent
  precision, capped amounts, required net income and proposed rent,
  no unsupported fields, limited number of imported goals.
- **Privacy:** No account identifiers, passwords, bank connection, direct
  AI calls, financial URL query parameters or financial analytics events.
  CSV exports contain entered amounts because users explicitly download
  them; warn users to store exports privately.

## Limitations that must appear in testing

- No bank verification, comprehensive budgeting guarantee, dated bill
  ledger, salary growth, inflation, tax treatment, interest/tax on savings
  in this simplified comparison, or changes in future spending habits.
- Some move-in fees and security deposits may be refundable. The alpha
  models them as a liquidity outflow without forecasting refunds. First
  month's prepaid rent can be double-counted unless the user adjusts
  assumptions carefully.
- Income/expenses that were not entered are unknown, even if the monthly
  comparison temporarily models them as zero; a checked completeness box
  is not proof of complete financial accounts.
- The scenario is a simulation, not a bank balance forecast. Negative
  checking balances are cash shortfalls, not approved overdrafts.
- `st.session_state` is temporary server-side session state, not durable
  encrypted user storage. Workspaces persist only when explicitly
  exported to the user's device and later reimported.
- The feedback link uses a **public GitHub issue** and requires a GitHub
  account. Users must not enter private amounts, names, addresses, or
  bank details. A frictionless anonymous form can be substituted after
  a suitable endpoint is approved.
- No usage analytics have been added. If added later, collect only
  opt-in, coarse event names, never amounts or free-text financial input.
- Streamlit is retained. No cloud AI is required or invoked in the new lab.

## Test and staging plan

Run locally:

```sh
git fetch origin
git switch alpha/decision-first-testing
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app.py
```

GitHub Actions on this branch runs the full pytest suite, including:
financial invariants, empty and incomplete inputs, large and invalid
numbers, negative monthly margin, low/zero cash, cash versus savings
funding consent, immutability, optional goal conflict, CSV and Streamlit
page smoke tests. Review [PR #1 checks](https://github.com/jbj-02/moneylab/pull/1/checks).

For a real browser and mobile-device check before merging:

- Open Home on a phone-width browser: decision choice buttons, readable
  contrast, keyboard focus order, sidebar navigation and no horizontal
  overflow.
- Choose Move Out; use fictitious sample; compare and download CSV.
- Switch to own numbers: sample results must disappear; leave unknown
  amounts blank; compare and read the flagged assumptions.
- Enter a rent-heavy proposal creating a negative monthly margin;
  check that no positive "affordable" verdict appears.
- Set checking below upfront funds. First run without savings permission,
  then enable it and compare. Confirm a shortfall is never auto-financed.
- Enter a goal through My Money, opt into importing it in the moving lab;
  verify the goal can change and is never modified by the simulation.
- Go back, add and edit blocks, change an existing expense, export/import
  workspace JSON, and verify other pages still run.
- Open the public feedback form, verify the public-data warning, and
  submit only *fictional* reproduction details.
- Run keyboard-only navigation and test a screen reader if available.
  **Automated Streamlit AppTest does not substitute for these visual checks.**

### Alpha staging

Create a **separate** Streamlit Community Cloud app using:

- Repository: `jbj-02/moneylab`
- Branch: `alpha/decision-first-testing`
- Entry point: `app.py`

Do not reconfigure the existing production app to this branch and do not
merge PR #1 until the staged UI has been visually checked with sample data
on desktop and mobile. Streamlit should deploy commits on the selected branch
automatically when branch-specific deployment is configured.

## Recommended user-test script

Have 5–10 students/recent graduates, using *fictional* information, attempt
a move comparison with minimal prompting. Observe, rather than instruct:

1. Can they find the moving decision in under 30 seconds?
2. Can they reach a meaningful comparison in about five minutes?
3. Do they understand the difference between recurring cash flow and
   upfront cash?
4. Do they recognize missing information without interpreting it as
   a verified zero expense?
5. Can they change one figure and explain the impact?
6. Can they export or provide feedback without revealing sensitive data?

Record completion times, the biggest confusion points, and whether users
would use the result before an actual money decision. Revisit the 5-minute
target with evidence rather than claiming it has already been proven.

## Deferred until validation

Bank synchronization, account registration, paid AI, app-store packaging,
long-term cloud financial storage, automated user analytics, actual dated
cash timing, deposit refunds and prepaid-rent handling, broad multi-person
budgets, and investment/credit recommendations.
