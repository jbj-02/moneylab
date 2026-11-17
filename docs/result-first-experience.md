# Result-first MoneyLab

This redesign starts from `main` at `533dbe4`. It replaces the dashboard's
recommendation cards with a plain-English goal answer, one verified experiment
and one primary **Test this change** action. No financial engine or projection
formula was replaced.

## What the user sees

The welcome page has three starting points: a savings goal, a purchase, or a
move. Savings setup asks for the goal, monthly money, then cash, savings and
debt. Dining out is separate from groceries so a proposed change can name a
specific recorded expense. Answers survive Back; setup cannot replace an
existing profile. Goal savings are subtracted from total savings exactly once.

My Plan first states the target, deadline and projected gap, or explains that
the goal is on track. It then offers one modeled change. **Edit figures** holds
the shared profile; **Test a decision** uses it for purchases, expenses, income,
debt and moves. Older bookmarks remain reachable, while overlapping goal,
simulator and language-entry screens stay out of the main navigation. Optional
plain-language decision entry is available on the decision page.

The comparison puts **Current plan** beside **With this change**. Both show the
goal at its labeled deadline and the first month's money left after bills,
debt and saving. It states the difference in dollars. A later deadline is
explicitly a change in time; a smaller target is explicitly a change in size.
Exact edits remain visible, as do cash risks and losses to another goal.
Charts, arithmetic, assumptions and optional stress tests sit under **How we
calculated this**. Other adjustments and progress checks are available without
competing with the first result.

## Each suggestion is a simulated experiment

`goal_result.py` is independent of Streamlit. It consumes the same validated
blocks as the existing engine and never mutates them.

1. Missing figures produce a concrete question instead of an unsupported precise gap. No extra
   commitment is suggested until those named unknowns are resolved.
2. If the goal is on track, test a lower sufficient contribution when possible,
   or test keeping the existing pace. This case says **Test this plan** when no
   edit is proposed.
3. If enough monthly money is left, test setting aside the calculated additional
   amount before suggesting any spending cut.
4. Otherwise, search for a cut to an existing, clearly named discretionary
   expense and redirect it to the goal. Candidate cuts are cent-level engine
   simulations. The request cannot exceed current saving plus recorded monthly
   room plus that cut. A cut must actually reach the target and must not worsen
   any simulated cash shortfall.
5. If no bounded expense test works, offer a later date actually reached by the
   recorded plan, searching at least 120 months or the longest entered goal
   deadline, up to the engine's 600-month limit. When no date is reached, ask for
   a recorded adjustment rather than inventing income or a date.

Automatic cuts are limited to dining, takeaways, restaurants, entertainment,
subscriptions or coffee entries. Bundles containing rent, housing, groceries,
utilities, insurance, debt or bills are excluded. The cap is half the recorded
entry and $150/month, whichever is smaller. These are explicit product
heuristics for a manageable experiment, not a claim that a cut is practical for
every person. The rule is disclosed in the calculation detail. Users can still
test their own reduction to another recorded expense.

Income routing, actual loan payments, account ordering, interest and competing
goals remain part of the engine simulation. Direct deposits and reductions to
another goal remain visible. First-month money left is labeled as such; it is
not a daily cash forecast or proof that all later months are the same.

## Unknown is different from zero

Blank setup fields retain missing-information markers. The result asks for the
first specific missing figure; Edit figures allows resolving all of them.
Submitting a blank answer is rejected. Explicitly entering $0 resolves only
that field. The whole-plan confirmation no longer erases unrelated unknowns.
Debt can be confirmed absent only when that does not contradict a recorded
positive loan. All debt details must be recorded before that alternative can
be selected. Backups and local storage preserve these markers, including the
new dining category; existing workspace versions still import.

## Testing does not change the plan

The prefilled comparison is detached from the source profile. Exporting during
exploration returns the original figures. Editing pay, spending or another
source figure invalidates an earlier comparison; a stale proposal cannot be
applied. Complete figure review and a separate explicit approval remain
required. Approval saves the exact edits and selected schedule, after which
progress checks continue to work. Discarding a test preserves the profile.

A new purchase visitor uses a single temporary form. The calculation does not
create financial entries or offer to apply a synthetic snapshot. Existing
purchase drafts and their frequencies still export and restore. Visitors with
a profile reuse their recorded figures. The move workflow likewise reuses the
profile when available; the welcome-page move entry starts with blank personal
inputs rather than prefilled fictional money.

## Frontend decision

Streamlit remains a reasonable implementation for this academic product: the
new experience uses native inputs, navigation, forms and explicit session state,
with no added runtime dependency. The result service is UI-independent and can
back another frontend. A React migration would add API, hosting and state
boundaries without directly improving the result's clarity. Revisit it if user
testing shows reruns, mobile interaction or state continuity limit completion.
Keeping Streamlit is a current tradeoff, not a permanent requirement.

## Verification and screenshots

The existing Python suite runs alongside new engine and UI acceptance tests.
`tests/browser_smoke.py` retains onboarding, edits, purchase immutability,
shortfalls, moving, custom expense redirection, stress tests, approval, progress,
and local persistence/deletion coverage. `tests/result_first_browser.py` adds
desktop and mobile journeys for a rescued goal, an on-track goal, an unreachable
deadline with a real later date, missing income, and a direct purchase. It
checks back navigation, source edits, stale approval, exported originals,
explicit zeros and exact applied contributions. CI runs both scripts.

The fictional rescue example starts with $3,620 saved toward $5,000 in six
months and $100/month planned. Income is $2,400 and spending is $2,300,
including $300 dining out. The original goal projection is $4,220, a $780 gap.
Reducing dining by $130/month and saving $230/month produces $5,000 at the
deadline; money left stays $0. After the user explicitly edits pay to $2,500,
the recalculated test uses $100 of monthly room plus a $30 dining cut. The
earlier $130-cut proposal is blocked as stale.

Before screenshots use the baseline checkout; after screenshots use the feature
branch at the same viewport widths with fictional data. They demonstrate the
implemented branch, not a production deployment. See the screenshot gallery
linked from the pull request. Tests cannot establish whether a real first-time
budgeter understands the result; a short user comprehension study is the next
product check. Monthly timing, manual balances and session-only hosted storage
remain limitations.
