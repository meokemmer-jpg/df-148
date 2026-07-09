from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class StressTestReport:
    liquid_assets: float
    monthly_expenses: float
    monthly_income: float
    monthly_burn_rate: float
    runway_days: float
    auto_liquidation: bool = False
    liquidation_proceeds: float = 0.0


def _to_non_negative_float(value: float, name: str) -> float:
    number = float(value)
    if number < 0:
        raise ValueError(f"{name} must be >= 0")
    return number


def _to_positive_float(value: float, name: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError(f"{name} must be > 0")
    return number


def _asset_amount(asset: Mapping[str, Any]) -> float:
    if "amount" not in asset:
        raise KeyError("asset amount is required")
    return _to_non_negative_float(asset["amount"], "asset amount")


def _is_liquid(asset: Mapping[str, Any]) -> bool:
    return bool(asset.get("liquid", asset.get("is_liquid", True)))


def total_liquid_assets(assets: Iterable[Mapping[str, Any]]) -> float:
    total = 0.0
    for asset in assets:
        if _is_liquid(asset):
            total += _asset_amount(asset)
    return round(total, 2)


def liquidation_proceeds(
    assets: Iterable[Mapping[str, Any]],
    liquidation_haircut: float = 0.25,
) -> float:
    haircut = _to_non_negative_float(liquidation_haircut, "liquidation_haircut")
    if haircut >= 1:
        raise ValueError("liquidation_haircut must be < 1")

    proceeds = 0.0
    for asset in assets:
        if not _is_liquid(asset) and bool(asset.get("auto_liquidatable", False)):
            proceeds += _asset_amount(asset) * (1.0 - haircut)
    return round(proceeds, 2)


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


def load_assets(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if isinstance(payload, dict):
        payload = payload.get("assets", [])
    if not isinstance(payload, list):
        raise ValueError("asset file must contain a list or an object with an assets list")

    assets: list[dict[str, Any]] = []
    for asset in payload:
        if not isinstance(asset, dict):
            raise ValueError("each asset must be an object")
        assets.append(asset)
    return assets


def run_liquidity_stress_test(
    assets: Iterable[Mapping[str, Any]],
    monthly_expenses: float,
    monthly_income: float = 0.0,
    *,
    expense_multiplier: float = 1.0,
    income_multiplier: float = 1.0,
    liquidation_threshold_days: float = 30.0,
    liquidation_haircut: float = 0.25,
) -> StressTestReport:
    asset_snapshot = list(assets)
    stressed_expenses = round(
        _to_non_negative_float(monthly_expenses, "monthly_expenses")
        * _to_positive_float(expense_multiplier, "expense_multiplier"),
        2,
    )
    stressed_income = round(
        _to_non_negative_float(monthly_income, "monthly_income")
        * _to_non_negative_float(income_multiplier, "income_multiplier"),
        2,
    )

    liquid_assets = total_liquid_assets(asset_snapshot)
    burn_rate = calculate_monthly_burn_rate(stressed_expenses, stressed_income)
    runway_days = calculate_cash_runway_days(liquid_assets, burn_rate)

    threshold = _to_non_negative_float(liquidation_threshold_days, "liquidation_threshold_days")
    proceeds = 0.0
    auto_liquidation = burn_rate > 0 and runway_days < threshold
    if auto_liquidation:
        proceeds = liquidation_proceeds(asset_snapshot, liquidation_haircut)
        liquid_assets = round(liquid_assets + proceeds, 2)
        runway_days = calculate_cash_runway_days(liquid_assets, burn_rate)

    return StressTestReport(
        liquid_assets=liquid_assets,
        monthly_expenses=stressed_expenses,
        monthly_income=stressed_income,
        monthly_burn_rate=burn_rate,
        runway_days=runway_days,
        auto_liquidation=auto_liquidation,
        liquidation_proceeds=proceeds,
    )


def run_liquidity_stress_test_from_file(
    asset_file: str | Path,
    monthly_expenses: float,
    monthly_income: float = 0.0,
    **stress_options: Any,
) -> StressTestReport:
    return run_liquidity_stress_test(
        load_assets(asset_file),
        monthly_expenses,
        monthly_income,
        **stress_options,
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
