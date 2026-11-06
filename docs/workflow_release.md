# MoneyLab workflow, results, and UI release — November 2026

This document describes the implemented version on the workflow development
branch. It does not imply that the Streamlit public deployment was inspected.

## Workflow

**Primary navigation:** Home, Decisions, My Money, Goals. Moving Out,
Quick Start, Learn, Settings/data and Classic Simulator keep their existing
route paths, but are discoverable through context-appropriate links and
secondary navigation.

- Home starts with Smart Decisions' local plain-English description or
  decision shortcuts. Existing parser-reviewed income/rent carry across to
  Moving Out, and unknown entries remain blank.
- Decisions links to Moving Out. When My Money has blocks, users can explicitly
  compare with their profile or use a temporary financial snapshot.
- Moving Out offers fictional numbers, personal manual entry, or "Use My Money
  figures". The profile adapter asks which existing expense represents
  **current** housing, sums recorded living expenses and loan payments, and
  deliberately excludes retirement and dedicated goal balances.
- The existing full profile is *never* overwritten by running a hypothetical
  scenario. Profile updates are reviewed **after** comparison: the reverse
  mapper previews new and existing blocks, forbids ambiguous updates, and
  requires individual approval. Proposed rent is never imported as current
  housing. Existing loan blocks block new duplicate loan-payment expenses.
- The existing Quick Start four-step wizard retains skip options and backward
  navigation; users who begin Quick Start from a decision return to that
  decision after approving blocks.

## Result trust and calculations

- All amount calculations remain in the validated Decimal project_blocks()
  engine and moneylab.moving. The model distinguishes missing (None) from
  zero entries. Blank costs are modeled as zero *for comparison only*, with
  the actual missing set disclosed next to the results.
- The "Included in this comparison" breakdown exposes current recurring
  costs, proposed costs, upfront charges, checking, savings and their source.
  It reconciles each headline to the underlying elements.
- **Recorded liquid funds** means entered checking plus savings classified
  as accessible. Users must decide if savings are earmarked; dedicated goal
  balances do not count. **Eligible upfront funds** are checking plus
  savings only if the user expressly allows savings for moving costs.
- Monthly remainder is net income less recorded monthly expenses and debt
  minimums, **before** optional transfers toward goals. Savings transfers
  are not counted a second time as living costs. Profiles with separately
  modeled loans exclude similarly named debt-payment expense blocks from
  the moving summary to prevent likely double counting, with a warning.
- Loan minimums and other living expenses are monthly averages. The moving
  simulator does not model a loan stopping after its future payoff, exact
  utility due dates, actual rent cycles, refundable deposits, investment
  performance, taxes or a verified bank balance. These are important
  limitations of the 6/12/24-month comparison.
- Moving results have an immediate takeaway, a cash breakdown, a
  chronologically ordered Altair chart (Stay consistently blue, Move
  consistently orange), an exact-value table and optional risk/methodology
  details. Negative balances are unfunded shortfalls, not credit offers.
- The original comparison remains in session during editable alternative
  scenarios. Rent, roommate share, upfront costs, and simple "delay/save"
  arithmetic are presented as **hypotheses**, not personalized
  recommendations. Changing a source or original assumption invalidates the
  old calculated result. Imported profile/goal changes also invalidate
  dependent results.

## Workspace persistence

The sidebar makes **Save / restore workspace** visible.

- Version 3 JSON includes existing financial blocks, up to 20 saved
  single-expense What-if scenarios, and up to three validated draft
  decisions (currently one Moving Out and one cost decision). Inputs may
  include private financial amounts. Save and store the exported file
  privately. No auto-save is implied.
- v1 profile-only and v2 profile/scenario JSON files remain importable.
- Imported files have strict schema, amount, size, version and reference
  checks. Importing requires explicit replacement confirmation and is
  validated **before** replacing session profile data.
- Draft decisions restore to editable forms, never to a cached or
  apparently current comparison. Natural-language descriptions, account
  credentials and model-generated calculations are not saved in v3.
- Workspace import/export intentionally does not create accounts, a cloud
  database or client-side browser storage.

## Private feedback configuration

A dedicated **Feedback** page asks three questions: what the tester tried,
what was confusing or wrong, and what would help. It does not attach any
financial figures, descriptions, profile data, email or identifying
metadata from MoneyLab automatically. The user is told not to paste
personal amounts or information into feedback.

Private submission uses a low-maintenance **Formspree inbox**. No arbitrary
URLs are permitted: the server validates the form endpoint must match
\`https://formspree.io/f/FORM_ID\`. The Streamlit server sends the three
comments and an app label in an HTTPS JSON POST. A successful message
appears **only** after a 2xx HTTP response.

**To enable:**

1. Create a new form at https://formspree.io/ and verify the inbox
   destination. Configure access, retention and spam controls to match
   your needs. The inbox belongs to the app owner, not GitHub.
2. Copy the exact form endpoint URL (e.g. \`https://formspree.io/f/abc123\`).
3. In Streamlit Community Cloud, open your MoneyLab app's Settings →
   Secrets and enter:

   \`\`\`toml
   MONEYLAB_FEEDBACK_URL = "https://formspree.io/f/YOUR_FORM_ID"
   \`\`\`

4. Restart or redeploy the Streamlit app if required and submit a
   **fictional** test message. Verify actual delivery in Formspree's
   submission dashboard before claiming that private feedback works.

The repository intentionally has no working personal form endpoint
or credentials. Until configured, the interface explicitly refuses to
claim submission and offers a downloadable **unsent** feedback draft.
This is not an anonymous hosted feedback collection service until set up.

References: https://help.formspree.io/articles/building-your-form/submit-forms-with-javascript-ajax
and https://help.formspree.io/articles/form-and-project-settings/system-limits

## Engineering verification

Run:

\`\`\`sh
python -m pip install -r requirements.txt
python -m compileall -q app.py moneylab tests
python -m pytest -v
\`\`\`

CI checks all calculations, parser behavior, existing profile, goal and
Quick Start functions, versioned workspace compatibility, duplicate-safe
profile updates, private-feedback validation and the Streamlit page tests.

The \`Browser UI smoke\` workflow additionally runs **real Chromium** at
1280px desktop and 390px mobile widths against a locally launched Streamlit
app, checking Home, Moving Out, result breakdown, editing/recalculation,
Settings, and horizontal overflow. Screenshots and logs are saved as
fictional test artifacts for 7 days.

**Not verified by these automated checks:** the user-hosted public
\`https://moneylab-dev.streamlit.app/\` deployment, every browser or assistive
technology, actual personal bank data, private Formspree delivery without
configuration, or a statistically meaningful 3–5-minute task completion
time. Those require manual live testing and alpha users.

## Deferred decision types

Car purchase/financing, job offer and debt-versus-liquidity remain the
next templates. Shared scenario changes are available, but no additional
specialized calculations or definitive financial recommendations have
been introduced in this pass.
