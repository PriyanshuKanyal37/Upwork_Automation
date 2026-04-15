from __future__ import annotations

from decimal import Decimal

from app.application.ai.contracts import ProviderName

_PER_1M_COST_INPUT: dict[ProviderName, Decimal] = {
    ProviderName.OPENAI: Decimal("0.75"),
    ProviderName.ANTHROPIC: Decimal("3.00"),
    ProviderName.GEMINI: Decimal("1.00"),
}

_PER_1M_COST_OUTPUT: dict[ProviderName, Decimal] = {
    ProviderName.OPENAI: Decimal("4.50"),
    ProviderName.ANTHROPIC: Decimal("15.00"),
    ProviderName.GEMINI: Decimal("3.00"),
}


def estimate_call_cost_usd(*, provider: ProviderName, input_tokens: int, output_tokens: int) -> Decimal:
    input_price = _PER_1M_COST_INPUT.get(provider, Decimal("0"))
    output_price = _PER_1M_COST_OUTPUT.get(provider, Decimal("0"))
    input_cost = (Decimal(max(0, input_tokens)) / Decimal(1_000_000)) * input_price
    output_cost = (Decimal(max(0, output_tokens)) / Decimal(1_000_000)) * output_price
    return (input_cost + output_cost).quantize(Decimal("0.000001"))

