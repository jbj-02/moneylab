# MoneyLab: from calculators to a financial plan

The subsequent [action-plan release](action-plan.md) extends the recommendations, comparisons, uncertainty testing and progress tracking described here. This document records the original overhaul and its validation.

## Product decision

MoneyLab helps someone turn their recorded finances into a practical next step,
then test that step against the rest of their plan. Its advantage over a blank
spreadsheet is the connection between a goal, a fundable saving pace, competing
commitments and a decision's consequences. It is not a transaction tracker or a
substitute for checking actual loan terms and account balances.

The academic project's Python engine and calculation regressions remain assets.
Neither the old interface nor Streamlit is a permanent product requirement.
This iteration replaces the main workflows, rather than adding another layer
of navigation on top of them. The existing live deployment stays on `main`
until the pull request is reviewed and merged.

## Critical audit

The audit used the current `main` checkout at `2a6afa4`, its page entry points,
setup modules, recommendation logic, workspace handling and regression suite.
All 413 original tests passed before changes. The public URL returned HTTP 200;
interactive inspection in the downloaded Chromium was blocked by a proxy CA
trust error. This document does not claim live-deployment UX verification.

| Problem in the previous experience | Replacement |
| --- | --- |
| A plan mostly summarized metrics and linked to another tool | Ranked, calculated actions with an inspectable alternative |
| Goals were displayed separately from decisions | Goals, deadlines and monthly funding appear in the plan and in comparisons |
| Setup started with financial inputs; multiple setup methods competed | One goal-first, three-step setup with explicit approval |
| Some setup paths turned skipped inputs into omitted zero-like values | Unknown fields survive setup and workspace export; incomplete estimates stay preliminary |
| Session-only storage required a manual file to return | Optional local continuity, storage interface, and a documented authenticated hosted design |
| Long cards, technical block types, routing and legacy tools competed for attention | Compact grouped financial rows, direct edits, four primary destinations |
| Single-screen calculation results disappeared or required manual edits elsewhere | Detached comparisons persist across page navigation until discarded, applied or invalidated |

Public product references informed interaction patterns, not visual branding:
[YNAB goal tracking](https://www.ynab.com/features/goal-tracking) connects a target
to a saving pace; [YNAB Home](https://support.ynab.com/spotlight-BkdHBZUokg)
emphasizes a current goal; [Monarch flex budgeting](https://help.monarch.com/hc/en-us/articles/32125337244052-Using-Flex-Budgeting)
reduces the initial numbers to interpret; and
[Monarch goals](https://help.monarch.com/hc/en-us/articles/44373110771860-Goals-in-Monarch)
connects exploration with the plan. MoneyLab does not implement their bank-linked
transactions, goal allocation or account authentication.

## Information architecture and design

Primary destinations are **My Plan**, **My Finances**, **Explore Decisions** and
**Settings & data**. Setup is a task, not a competing destination.

1. Choose a priority and, if relevant, a target and deadline.
2. Record monthly take-home pay and familiar spending categories.
3. Record balances, the portion of savings assigned to the goal, a saving pace
   and optional debt details; approve the preliminary plan.

Back retains submitted answers. Blank means unknown; explicitly entered zero
means known zero. A goal's starting funds are deducted from total savings during
setup so the same dollars are not counted twice. Later manual goal/account edits
are separate pots; their forms explain that users must avoid duplicate balances.
Multiple loans and goals can be added after setup.

The plan leads with one priority and three current figures. It shows up to two
additional actions, goal progress, the projected outlook, and an optional text
decision entry. The signed monthly remainder remains visible for a user whose
budget does not balance. There is no invented financial health score.

The visual system uses deep teal, warm neutral backgrounds, restrained amber
comparison accents, consistent rounded surfaces and real native controls.
Status text accompanies color. Charts label units and provide tooltips. Focus
outlines and reduced-motion preferences are preserved. CSS targets Streamlit
elements and needs review after framework upgrades; no HTML imitates an
interactive form control.

## Feature disposition

| Previous feature | Decision | Result |
| --- | --- | --- |
| Python projections, loan math, exact Decimal values | Keep | Used by every new calculated outcome |
| My Plan dashboard | Redesign | Priorities, actionable goal gaps and visible projection |
| Separate Goals navigation | Merge | Goals live in My Plan; old `/goals` opens that experience |
| Four-step guided setup, text setup and optional AI setup | Replace in primary UX | One three-step flow; old parser/calculation modules remain available for compatibility tests |
| Building block cards and reorder controls | Redesign | Familiar grouped rows and direct item edits |
| Classic Simulator | Remove from primary UX | Old bookmarked route and reusable math preserved |
| Moving Out lab | Keep and integrate | Launch from decisions with the existing profile selected; reviewed mapping stays explicit |
| Purchases, commitments, expense and income changes | Merge | One compare workflow using the same baseline |
| Reserve-readiness and goal calculators in Decisions | Merge | Goal work belongs to the plan, eliminating the extra primary decision modes |
| Extra loan-payment comparisons | Add | Interest, debt and goal effects evaluated together |
| Plain-English decision input | Keep optional | Deterministic parser, review before routing, no external AI required |
| Account routing, learning catalog, legacy expense-scenario editor | Defer from primary UX | Existing data, logic and bookmarked legacy pages are retained; no destructive migration |
| Manual JSON backup and CSV projection export | Keep | New format preserves unknowns and reads older formats |
| Authenticated cross-device saving | Defer implementation | Storage boundary and explicit release requirements below |

## Recommendation and approval model

`planning.py` imports no Streamlit code. It uses `project_blocks` to rank missing
review, cash shortfalls, growing debt and missed goals. A goal's minimum monthly
contribution is found by a search over cents, rerunning the same projection for
each candidate. Other transfers, direct deposits, debt payoff and unfunded cash
recovery remain in that simulation. A contribution one cent below the reported
minimum is tested in the regression suite.

If a deadline is not fundable, the model reports the maximum that available
monthly money can reach. Users can compare a later deadline or choose their own
reduction to an expense actually recorded. The product never declares a named
expense optional and never invents new income. Suggestions are alternatives:
two suggestions may need the same money. Applying one causes the others to be
calculated again.

Each comparison displays its concrete edits, monthly remainder, ending cash,
debt, modeled interest, chart, every goal's result and cash-shortfall warnings.
Goal comparisons label each plan's own deadline. Account contributions can be
limited by available monthly money; planned saving is not guaranteed funding.

A preview opens a focused comparison screen immediately and remains reachable
through **Review pending alternative** while the user navigates elsewhere.
It owns a detached copy and a source-profile signature. Applying it
requires reviewed complete figures and a separate explicit approval. A changed
source blocks approval. Apply replaces the modeled inputs, not real accounts,
and invalidates prior review. Discard leaves the current plan untouched.
The existing detailed move workflow still uses its reviewed current-figure
mapping; it does not automatically apply a proposed move to the real plan.

## Frontend architecture decision

**Retain Streamlit for this iteration; do not treat that as a permanent choice.**
The new workflows work with native forms, dialogs, navigation and Altair charts.
Keeping one Python deployment is proportionate for the academic project today.
Switching solely for spacing or colors would spend effort without validating
whether the planning experience is useful. A future migration is explicitly
allowed when its user benefit outweighs the cost.

| Approach | Product advantages | Engineering cost and limits | Decision |
| --- | --- | --- | --- |
| Native Streamlit + small shared design layer | Fast iteration, one Python runtime, same engine and tests | Rerun model, limited navigation/layout control, CSS upgrade sensitivity | Implemented |
| A few custom Streamlit components | Rich chart interactions or specialized controls without replacing the app | Additional component state and accessibility contracts; two runtimes for each component | Consider for a demonstrated interaction gap |
| React/TypeScript frontend + Python API | Full responsive control, richer editing and onboarding, persistent client drafts, conventional auth integration | API contracts, auth/session security, two build systems and deployments; financial logic must stay in Python | Evaluate with a representative prototype before committing |

Reopen this decision when mobile task tests repeatedly fail because of framework
behavior; preserving in-progress work across sessions requires an awkward
component workaround; accounts and multi-device navigation become central; or
interactive scenario comparison needs exceed native components. Measure setup
completion, edit-and-compare success, task time and maintenance cost. Prototype
setup → goal gap → preview → apply in the proposed frontend, using these same
Python services and fictional acceptance fixtures. Choose the better product,
even if that requires replacing the shell.

Boundaries now are `engine.py`/`blocks.py` for financial math, `planning.py` for
plan actions and alternatives, `plan_setup.py` for setup validation,
`profile_store.py` for serialization/storage, `plan_session.py` for Streamlit
state, `design.py` for visual primitives, and `plan_ui.py` for task flows.
Older calculation modules were not rewritten. The older `ui_app.py` is still
used by legacy pages and shared item-edit dialogs; extracting those dialogs is
a future cleanup, not a prerequisite for a different frontend.

## Persistence implemented here

The public default remains session-only and says so. No database, anonymous
workspace ID or browser token quietly turns on shared-host saving.

For a **single person on a local computer**, explicitly opt into SQLite:

```sh
mkdir -p work/local-profile
MONEYLAB_LOCAL_STORE="$PWD/work/local-profile" python -m streamlit run app.py \
  --server.address=127.0.0.1 --browser.gatherUsageStats=false
```

Do not expose this mode through a public proxy or tunnel, and do not use it on a
shared computer. A loopback-only server setting is required; unset/shared
addresses fail closed. The directory is mode 0700 and the file 0600. The data is
plaintext: this adapter provides no login or application-level encryption.
Use the computer's disk encryption if needed. It is development persistence,
not account-based storage.

Validated snapshots save as the profile or supported drafts change and load
when a new local session starts. Optimistic revisions reject stale writers.
Deletion clears session financial forms and stored payload, retains a conflict
generation so an older session cannot resurrect it, and enables SQLite secure
deletion for replaced pages. Filesystem backups and previously exported files
remain outside the application's deletion scope.

The save status reports failure and offers a backup if writing fails. It never
reports successful saving after a revision conflict. A pending alternative is
session-only and is not exported. Supported historical move/cost drafts and
named expense scenarios remain exportable. Workspace version 4 wraps the
previous version 3 workspace with priority, unknown fields and an example-data
marker. Versions 1–3 import without losing financial entries. Review is renewed
after restore. Older MoneyLab releases cannot read v4 files, so keep an original
backup before adopting the new export format.

## Recommended hosted solution and remaining implementation

Use Supabase Auth and Postgres with row-level security for an initial small
public release. Its [pricing](https://supabase.com/pricing) currently includes a
free plan with a 500 MB database, but free projects can pause and should not be
treated as a production availability or backup guarantee. Confirm current
quotas, email delivery, retention and operating costs before launch. A managed
Postgres/auth service reduces operational work compared with maintaining a
database, password flow and email delivery ourselves. Browser-local saving
cannot provide cross-device continuity and can expose financial data on shared
devices; a shared SQLite file does not supply per-user authorization.

The authenticated adapter is deliberately not represented as working today.
Before enabling hosted saving:

1. Implement sign-in, verified sessions, logout, session expiry and recovery.
   Derive owner identity from verified authentication, never an editable form,
   query parameter or user-supplied workspace identifier.
2. Store one versioned JSON snapshot per owner with an optimistic revision and
   server timestamp. Enforce ownership in the database using
   [RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)
   for reads, writes and deletes. Use user-scoped credentials; never let normal
   requests bypass RLS using a service-role key.
3. Test two real authenticated test identities against the database: each must
   fail to read, update, overwrite or delete the other's row. Test expired
   sessions, concurrent edits, outages and sign-out state clearing.
4. Provide verified export, account/profile deletion, a retention policy and a
   backup/restore procedure. Keep financial payloads out of application logs
   and analytics. Configure secrets, callback URLs, TLS and email delivery in
   the deployment, not in source control.
5. Add the hosted `ProfileStore` adapter and authenticated session boundary,
   then rerun browser journeys across reload and sign-in on another device.

No provider account, billable resource or live deployment was changed by this
overhaul.

## Validation and release

The Python suite covers old financial calculations and realistic new plan
cases: emergency-fund funding, infeasible deadlines, competing goals, existing
income routes, cash shortfalls, student-loan tradeoffs, explicit-zero setup,
double-counted savings, stale approvals, old imports, private local files,
revision conflicts and deletion. UI tests cover setup/back, approval,
comparison immutability, deletion and a returning local session.

`tests/browser_smoke.py` drives Chromium at 1440×1000 and 390×844. The journeys
exercise a graduate with a student loan and move-out goal, savings-pace preview
and approval, a major purchase, an unfunded budget, actual financial editing,
workspace upload/download and the legacy move comparison. Exported JSON is
checked to prove that exploring does not mutate the plan. Screenshots and
overflow checks are taken at meaningful steps. Optional local continuity tests
run against a second loopback server when `MONEYLAB_PERSISTENCE_TEST_URL` is set.
These are automated task checks, not a substitute for user research or a
complete accessibility audit.

Release through the dedicated development branch and PR. Keep `main` and the
existing live deployment available while review/CI complete. Review screenshots,
validate the authenticated-storage boundary before any public saving claim,
then merge deliberately. After deployment, run a separate live smoke check;
local verification does not verify Streamlit Community Cloud behavior.

Validation recorded for this overhaul:

| Check | Result |
| --- | --- |
| Original baseline suite | 413 passed before implementation |
| Final Python suite | 436 passed |
| Compile and patch whitespace checks | Passed |
| Graduate, savings/purchase, struggling-budget and move journeys | Passed in desktop and mobile Chromium, eight journeys total |
| Real dialog edits, imports, exports and immutable exploration | Passed in those browser journeys |
| Local plan reopened in a separate browser session | Passed |
| Local deletion acknowledged, then checked in another fresh session | Passed |
| Public URL | HTTP 200; interactive browser verification blocked by proxy CA trust |

The browser script explicitly opens and closes the native mobile sidebar. Its
screenshots cover actual narrow layouts, not resized desktop mockups.

Remaining work is authenticated hosted continuity, testing with actual target
users, richer multi-debt strategy selection, calendar-anchored deadlines,
automatic dated financial check-ins and fuller accessibility review. Current
projections use fixed monthly averages and illustrative rates, exclude tax and
daily bill timing, and fund savings in saved profile order. Do not imply those
limitations are a complete real-world affordability assessment.
