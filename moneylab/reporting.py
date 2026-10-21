"""Export MoneyLab calculation results without relying on the UI framework."""

import csv
from io import StringIO


EXPORT_FIELDS = (
    "month",
    "income",
    "living_expenses",
    "regular_loan_payment",
    "extra_loan_payment",
    "loan_payment",
    "interest_charged",
    "interest_paid_this_month",
    "unpaid_interest_this_month",
    "principal_paid",
    "net_cash_flow",
    "savings",
    "unfunded_shortfall",
    "loan_balance",
    "net_position",
    "cumulative_interest_charged",
    "cumulative_loan_payments",
)


def projection_to_csv(projection):
    """Return a UTF-8 CSV string, preserving money to exact decimal cents."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS, lineterminator="\n")
    writer.writeheader()
    for record in projection["monthly_records"]:
        writer.writerow({field: str(record[field]) for field in EXPORT_FIELDS})
    return output.getvalue()


def comparison_to_csv(comparison):
    """Export both strategies with a Scenario column for easy analysis."""
    output = StringIO()
    writer = csv.DictWriter(
        output, fieldnames=("scenario",) + EXPORT_FIELDS, lineterminator="\n"
    )
    writer.writeheader()
    for name in ("saving", "accelerated"):
        for record in comparison[name]["monthly_records"]:
            writer.writerow({
                "scenario": name,
                **{field: str(record[field]) for field in EXPORT_FIELDS},
            })
    return output.getvalue()
