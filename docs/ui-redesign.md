# MoneyLab experience redesign

This describes the previous three-part release. See [the product overhaul](product-overhaul.md) for the current workflows and architecture decision.

This branch groups the app around three jobs. **My Plan** is the landing page and separates recorded finances, forecasts and suggested actions. **My Finances** is the place to enter and edit data. **Explore Decisions** holds scenario comparisons.

## Before and after

| Previous experience | Redesigned experience |
| --- | --- |
| Home mixed decision shortcuts, onboarding links, account updates and check-in metrics | New users see one primary setup action and two decision shortcuts. Returning users see today's figures, projections and a next step in order. |
| Quick Start asked people to choose a setup mode before entering figures | The four-step guided flow opens immediately. Plain-English entry remains optional and uses the same review. |
| Goals had a separate primary navigation destination | Savings goals, timing and comparisons appear in My Plan. The existing Goals URL remains available. |
| Profile editing explained the engine's building blocks | My Finances groups editable records by what they mean to a user. Common examples and routing controls sit behind expanders. |
| Decisions presented profile source before the user's intent | Users pick a decision before choosing whether to reuse their profile or enter figures for that decision. |

The interface uses a restrained green palette, native controls with readable labels, compact sections and full-width actions on narrow screens. It uses the existing Streamlit components so navigation, keyboard behavior and session state follow the same platform conventions.

## Feature decisions

| Decision | Features |
| --- | --- |
| Keep | Python projection and decision engines, review before saving, manual editing, move-out and goal calculations, session workspace export/import, feedback |
| Redesign | Profile editor, plan overview, goal forecasts and contribution guidance, decision entry |
| Combine | Guided setup and optional text entry share the same confirmation step. Goal results are part of My Plan. |
| Remove from primary navigation | Standalone Goals and legacy paths such as Classic Simulator. Their URLs and underlying calculations are retained. |
| Defer | Dedicated car financing, income change and debt-versus-saving templates. The move and expense flows are the first journeys to validate. |

Goal adjustments use the existing deterministic goal simulator. My Plan asks users to review the underlying figures before showing a contribution increase. It checks the projected cash path and flags any other goal whose modeled result declines. Each adjustment is a separate scenario and requires the user to edit their plan if they decide to apply it.

## Walkthrough with fictional figures

1. **First visit.** Open My Plan and select **Set up my finances**. Enter take-home pay, continue through spending, and add the balances and goals you know. Review the proposed entries and select **Save selected details** to return to My Plan. An income-only profile still receives prompts for missing costs and cash.
2. **Moving out.** Use the move shortcut or Explore Decisions. Enter income, housing, living costs, cash and loan payments, then the proposed rent and upfront costs. Review the inputs and calculate. Add a cash cushion and compare how a spending cut changes the estimated timing.
3. **Emergency fund.** With $8,000 saved and $200 monthly contributions toward $10,000, My Plan projects ten months. A six-month target is $800 short. With sufficient recorded monthly room, the simulator shows an additional $133.34 per month after the user reviews their figures.
4. **Major purchase.** Choose the cost check in Explore Decisions. Enter a one-time cost and compare immediate checking, monthly room and affected goals. The scenario leaves the user's financial details intact.

This is a session-based planning tool. Workspace export is needed to keep a copy. Cash forecasts use recorded amounts and monthly estimates, and the app cannot infer missing bills. Browser smoke checks cover the entry screens and move-out flow. Real novice usability sessions, a full accessibility audit and the Streamlit Cloud deployment of this branch remain separate validation steps.
