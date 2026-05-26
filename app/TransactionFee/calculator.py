from decimal import Decimal, ROUND_HALF_UP
from .models import FeeRule, FeeType


def compute_fee(rule: FeeRule, transaction_amount: Decimal) -> Decimal:
    """
    Compute the fee for a given transaction amount against a FeeRule.
    Respects min_fee / max_fee caps and rounds to 4 decimal places.
    """
    amount = Decimal(str(transaction_amount))

    match rule.fee_type:
        case FeeType.flat:
            fee = rule.flat_amount

        case FeeType.percentage:
            fee = (amount * rule.percentage_rate / Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

        case FeeType.hybrid:
            pct_part = (amount * rule.percentage_rate / Decimal("100")).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            fee = rule.flat_amount + pct_part

        case _:
            raise ValueError(f"Unknown fee type: {rule.fee_type}")

    # Apply floor/ceiling caps
    if rule.min_fee is not None:
        fee = max(fee, rule.min_fee)
    if rule.max_fee is not None:
        fee = min(fee, rule.max_fee)

    return fee.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)