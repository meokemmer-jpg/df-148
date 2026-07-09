from __future__ import annotations

import importlib
import json
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

engine = importlib.import_module("148")


def _write_assets(path: Path, assets: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"assets": assets}), encoding="utf-8")


def test_df_148_discriminates_adversarial_liquidity_case_from_opposite_case(tmp_path: Path):
    opposite_assets = tmp_path / "opposite-assets.json"
    adversarial_assets = tmp_path / "adversarial-assets.json"

    _write_assets(
        opposite_assets,
        [
            {"name": "cash", "amount": 9000, "liquid": True},
            {"name": "settled receivable", "amount": 3000, "liquid": True},
        ],
    )
    _write_assets(
        adversarial_assets,
        [
            {"name": "cash", "amount": 9000, "liquid": True},
            {
                "name": "restricted equipment",
                "amount": 3000,
                "liquid": False,
                "auto_liquidatable": True,
            },
        ],
    )

    opposite = engine.run_liquidity_stress_test_from_file(
        opposite_assets,
        monthly_expenses=4000,
        monthly_income=6000,
    )
    adversarial = engine.run_liquidity_stress_test_from_file(
        adversarial_assets,
        monthly_expenses=4000,
        monthly_income=6000,
        expense_multiplier=2,
        income_multiplier=0,
        liquidation_threshold_days=100,
    )

    assert opposite != adversarial
    assert math.isinf(opposite.runway_days)
    assert adversarial.runway_days < opposite.runway_days
    assert adversarial.monthly_burn_rate > opposite.monthly_burn_rate
    assert adversarial.auto_liquidation is True
    assert adversarial.liquidation_proceeds > 0

    report_path = Path(
        engine.write_report(adversarial, reports_dir=tmp_path / "reports", as_of=date(2026, 7, 9))
    )
    persisted = json.loads(report_path.read_text(encoding="utf-8"))

    assert persisted["auto_liquidation"] is True
    assert persisted["runway_days"] == adversarial.runway_days
    assert persisted["monthly_burn_rate"] == adversarial.monthly_burn_rate
