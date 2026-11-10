# Explainable action plans

MoneyLab now connects a finding to a realistic next step: why it matters, the
recorded money available, the options to compare, and the consequences of
choosing one. This builds on the [plan-first overhaul](product-overhaul.md).

## Audit and product decisions

The baseline was `main` at `69c333b`, with 436 passing tests. Code and local
browser review showed that the previous dashboard could calculate a goal gap
but did not explain funding or offer a coherent set of alternatives. Ranking
followed entry order among goals, preference was not editable, and approval
retained no dated schedule for later progress checks.

The public URL returned HTTP 200. Interactive live inspection was blocked by
the environment's proxy certificate trust; local browser testing uses the
actual application and does not establish live-deployment verification.

The revised sequence is:

1. **Understand the issue.** My Plan highlights one next action and up to two
   secondary actions. A short explanation states why each appears in that order.
2. **Review the reasoning.** Open “How MoneyLab worked this out” for the finding,
   calculation, proposed action, funding, outcome, tradeoffs and assumptions.
3. **Compare paths.** “View action & alternatives” opens a focused review task.
4. **Inspect consequences.** The comparison shows the exact edits, other goals,
   checking/cash, debt, interest, target dates and optional stress tests.
5. **Approve.** Complete reviewed figures and a separate approval remain required.
6. **Check progress.** The chosen contribution, target, dates and schedule remain
   visible in the plan; a recorded balance can be compared with that schedule.

The former custom goal editor is consolidated into the action-options screen.
The existing direct saving-pace preview, decision simulator and financial
editing workflows remain available.

## Ranking and preference

Upcoming unfunded cash and growing loan balances take precedence over optional
goal adjustments. Incomplete or unreviewed figures then require attention.
Other goal gaps use deadline order, with an editable preference available under
**Your priorities**:

- Balance priorities using deadline order.
- Put a selected goal first among optional actions.
- Prioritize a selected reserve goal or a user-entered checking cushion.
- Compare faster repayment of the highest entered interest-rate loan.

Preferences change the explanation and ranking, not the financial profile.
Cash and growing-debt risks stay ahead of the preference. An unknown or deleted
preferred goal does not become an invented account. The cash cushion is a soft
preference: a comparison warns when its cash trajectory is below the chosen
floor, and the user can inspect the tradeoff.

## Calculation behavior

Every option is a detached profile evaluated through `project_blocks`.
The financial engine itself is unchanged. The existing cent-by-cent contribution
search continues to include actual debt payments, income routes, other savings
requests, interest and recovery from unfunded cash.

The fictional $8,000 → $10,000 emergency fund illustrates the alternatives:

| Path | Monthly contribution | Deadline | Modeled outcome with sufficient monthly room |
| --- | --- | --- | --- |
| Keep current pace | $200 | 6 months | $9,200 at deadline; target in month 10 |
| Meet deadline | $333.34 | 6 months | $10,000.04 at deadline |
| Extend deadline | $200 | 10 months | $10,000 at the later deadline |
| Lower target | $200 | 6 months | $9,200 target; no new money created |

When the recorded budget cannot fund a deadline, the increased-contribution path
is omitted. Current timing, a later date when reached within the search horizon,
a smaller nonzero target and a custom adjustment remain available as supported
by the data. Timing searches normally cover at least 120 months or the longest
entered deadline, up to the engine's 600-month limit. A target not reached within
that horizon gets no fabricated date.

For a spending adjustment, users choose the recorded expense, the reduction,
and how much of that reduction to direct to the goal. Reducing an expense by
$200 and redirecting $133.34 means the goal's monthly contribution increases by
$133.34; $66.66 is not assigned to that goal. Other commitments may use released
room before it remains in checking. The model does not assume the expense is
optional or that the reduction is realistic for the user.

Funding explains the first-month identity: entered take-home minus living costs,
actual loan payments and modeled savings transfers equals the cash remainder.
It distinguishes requested goal transfers from transfers actually funded and
reports when the full request is not funded every month. First-month room is an
explanation, not a substitute for the full multi-month simulation.
Recorded direct deposits to a goal are shown separately from its planned
transfer. The searched contribution is additional to those existing deposits;
the breakdown reports their combined total rather than hiding the deposit.

Other goals are compared at a common original checkpoint as well as each
option's own deadline. Extending a deadline does not masquerade as creating
money. Other savings/investment accounts, debt, interest and cash shortfalls are
included where affected. Independent recommendations are alternatives, not a
combined allocation; approval changes the source profile and recalculates them.

## Uncertainty and approval boundaries

“What if things change?” tests a user-chosen higher expense, lower income or
one-time cost. The same dollar shock applies to each plan's own amount. Thus an
expense reduction in the proposed plan remains a reduction after an equal
expense shock. An unfunded upfront cost is reported as a gap, without assuming
borrowing or withdrawing earmarked goal savings.

Stress results have no apply action and cannot replace the approvable proposal.
The approval controls always refer to the unstressed exact edits. Changing the
assumption or proposal invalidates the displayed stress result.

Source and candidate signatures protect comparisons. A changed profile blocks
approval; altered candidate edits also require recalculation. A progress
comparison additionally checks the selected-schedule signature. Back navigation
retains the custom expense, redirection, target and date inputs independently
of page-widget cleanup. A changed source resets those drafts for recalculation;
discard leaves recorded figures untouched.

## Follow-through and dates

Approval saves a selected-plan record: the validated financial inputs, start
date, latest accepted check-in date and calendar deadlines. It stores inputs,
not cached projection claims. “Choose and track this plan” also allows a user to
select an unchanged current schedule.

A check-in compares the recorded goal balance with the balance produced by the
chosen schedule at whole elapsed months. A shortfall produces a calculated new
saving pace when fundable; otherwise the user is directed to timing, target or
chosen-spending alternatives. Balance and deadline updates are proposals until
approved, and they preserve the original selected schedule for later comparison.
Other account/debt balances are not replaced with predictions or claimed as
verified: they remain as recorded and should be updated if they changed.

Calendar deadlines stay fixed across repeated mid-month check-ins. The model
uses only whole future months before a deadline, which is conservative when a
partial month remains. A missed deadline is flagged. If less than one full month
remains, the engine's one-month recovery projection is explicitly insufficient
to establish whether the earlier calendar date can be met. Explicitly editing a
relative deadline is treated as an intentional change, not an automatic renewal.

Dates are estimates. No daily cash-flow engine, bank synchronization, inflation,
tax modeling or guaranteed investment result has been added. Monthly requests
continue until edited, including after a savings target is reached.

## Storage, migration and architecture

Workspace version 5 adds optional action preference and selected-schedule
metadata. Versions 1–4 still import; older profiles are never silently treated as
complete. Backups include the selected schedule, and the existing opt-in local
store persists it. Public deployments remain session-only and display that
status. Pending proposals and stress results are session-only. Deletion clears
the schedule and action state with the rest of the financial data.

The new `action_plan.py` and `progress.py` services have no Streamlit dependency.
`action_ui.py` renders the new task and composes it with the existing screens.
No new runtime dependencies or second deployment have been introduced.

Streamlit can support this workflow with native controls, forms and navigation,
so a frontend migration is not justified by this feature alone. Browser tests
wait for the selected assumption's new controls before entering a value;
Streamlit reruns are an actual interaction constraint. Input drafts, proposal
state and selected records are kept separate from widget cleanup. Revisit the
frontend if measured task completion, responsive interaction or maintaining
these boundaries becomes materially worse than a Python API plus a separate
frontend. The earlier architecture evaluation remains applicable.

## Validation and remaining work

Regression coverage includes fundable and infeasible deadlines, interest and
income routing, competing goals, shortfall/debt ranking, editable preference,
expense redirection, smaller targets, common checkpoint comparisons, decisions
that delay another priority, equal stress shocks, insufficient upfront cash,
incomplete inputs, stale source/candidate/schedule approval, schedule backups,
local reload, calendar boundaries and repeated progress checks.

The expanded Chromium journey follows the actual action workflow on desktop and
mobile: select an alternative, explicitly redirect an expense reduction, discard,
stress the recommendation, prove exploration did not alter an exported profile,
approve, export the chosen schedule, record a balance behind schedule, inspect
the revised pace and approve only that balance update. Existing onboarding,
editing, purchase, shortfall, move and local-deletion journeys remain in CI.

Remaining limitations are monthly rather than daily timing, manual balance
updates, mutually exclusive rather than jointly optimized recommendations,
limited comparison horizons and no authenticated hosted storage. Selected
schedules are not a transaction ledger or verified bank history. Testing with
target users and broader accessibility review remain necessary before making
strong usability or financial-outcome claims.
