"""Terminal value methods."""

from __future__ import annotations


def perpetuity_growth_terminal_value(last_fcf: float, wacc: float, growth_rate: float) -> float:
    """Calculate Gordon-growth terminal value with strict validity checks."""

    if wacc <= growth_rate:
        raise ValueError("WACC must be greater than terminal growth rate.")
    return last_fcf * (1.0 + growth_rate) / (wacc - growth_rate)


def exit_multiple_terminal_value(last_ebitda: float, exit_multiple: float) -> float:
    """Calculate terminal value from final-period EBITDA and an exit multiple."""

    if exit_multiple <= 0:
        raise ValueError("Exit multiple must be positive.")
    return last_ebitda * exit_multiple
