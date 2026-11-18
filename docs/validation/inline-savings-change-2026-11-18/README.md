# Inline savings change validation

All figures are fictional. The flow starts with a $4,000 goal in six months,
$2,500 saved, $3,000 take-home pay, $2,800 spending (including $350 dining),
and $200 monthly goal saving. Captures use 1440×1000 and 390×844 viewports.

| Scenario | Desktop | Mobile |
| --- | --- | --- |
| Recommended $50 cut, all redirected | [screenshot](desktop-prefilled-change.png) | [screenshot](mobile-prefilled-change.png) |
| $50 cut, cash kept available | [screenshot](desktop-keep-cash.png) | [screenshot](mobile-keep-cash.png) |
| $25 cut, all redirected | [screenshot](desktop-partial-change.png) | [screenshot](mobile-partial-change.png) |

The browser test also resets the scenario, exports the workspace, and verifies
that dining remains $350 and monthly goal saving remains $200 in the saved plan.
See [validation.json](validation.json).
