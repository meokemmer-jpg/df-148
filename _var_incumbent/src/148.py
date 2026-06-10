from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Any


@dataclass(frozen=True)
class StressTestReport:
    liquid_assets: float
    monthly_expenses: float
    monthly_income: float
    monthly_burn_rate: float
    runway_days: float
    auto_liquidation: bool = False


def _to_non_negative_float(value: float, name: str) -> float:
    number = float(value)
    if number < 0:
        raise ValueError(f"{name} must be >= 0")
    return number


def total_liquid_assets(assets: Iterable[Mapping[str, Any]]) -> float:
    total = 0.0
    for asset in assets:
        amount = _to_non_negative_float(asset["amount"], "asset amount")
        total += amount
    return round(total, 2)


def calculate_monthly_burn_rate(monthly_expenses: float, monthly_income: float) -> float:
    expenses = _to_non_negative_float(monthly_expenses, "monthly_expenses")
    income = _to_non_negative_float(monthly_income, "monthly_income")
    burn_rate = max(expenses - income, 0.0)
    return round(burn_rate, 2)


def calculate_cash_runway_days(liquid_assets: float, monthly_burn_rate: float) -> float:
    assets = _to_non_negative_float(liquid_assets, "liquid_assets")
    burn_rate = _to_non_negative_float(monthly_burn_rate, "monthly_burn_rate")
    if burn_rate == 0:
        return float("inf")
    return round(assets / burn_rate * 30.0, 2)


def run_liquidity_stress_test(
    assets: Iterable[Mapping[str, Any]],
    monthly_expenses: float,
    monthly_income: float = 0.0,
) -> StressTestReport:
    liquid_assets = total_liquid_assets(assets)
    burn_rate = calculate_monthly_burn_rate(monthly_expenses, monthly_income)
    runway_days = calculate_cash_runway_days(liquid_assets, burn_rate)
    return StressTestReport(
        liquid_assets=liquid_assets,
        monthly_expenses=round(float(monthly_expenses), 2),
        monthly_income=round(float(monthly_income), 2),
        monthly_burn_rate=burn_rate,
        runway_days=runway_days,
        auto_liquidation=False,
    )


def write_report(report: StressTestReport, reports_dir: str = "reports", as_of: date | None = None) -> str:
    report_date = as_of or date.today()
    output_dir = Path(reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"df-148-{report_date.isoformat()}.json"

    payload = asdict(report)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, allow_nan=True)
        fh.write("\n")

    return str(output_path)
# [CRUX-MK]
