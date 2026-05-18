
# K16: Concurrent-Spawn-Mutex (fcntl-based, Trinity-CONSERVATIVE 2026-05-17)
def k16_lock_or_exit(df_name: str):
    """Acquire exclusive lock or exit(3). Prevents concurrent DF runs."""
    import fcntl, os, sys
    lock_path = f"/tmp/df-trinity-{df_name}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        sys.exit(3)


# K13: External-Anchor-Mock-RFC3161 (Trinity-CONSERVATIVE 2026-05-17)
def k13_anchor(payload_hash: str) -> dict:
    """Mock RFC3161-style timestamp anchor."""
    from datetime import datetime, timezone
    return {
        "anchor_type": "rfc3161-mock",
        "iso_ts": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
    }


# K12: HMAC-SHA256-Provenance (Trinity-CONSERVATIVE 2026-05-17)
def k12_provenance(payload: bytes, key: bytes = b"df-trinity-conservative-v1") -> dict:
    """Returns payload_hash + HMAC-SHA256 signature."""
    import hashlib, hmac
    return {
        "payload_hash": hashlib.sha256(payload).hexdigest(),
        "hmac_sha256": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }

"""DF-148 engine for KPM-Liquidity-Stress-Test.

Tracks 3-Month-Cash-Survival dimensions with mock defaults and writes a JSON report.
"""

import re
import os
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timezone

DF_DIR = Path(__file__).parent
LOCK_DIR = Path("/tmp/df-148.lock")
DF_ID = "148"
DECISION_KEYWORDS_REGEX = re.compile(
    r"\b(entscheid[a-z]*|empfehl(?:e|en|t|st)|sollt(?:e|en|est)|recommend[a-z]*|decid[a-z]*|advis[a-z]*|propos[a-z]*)\b",
    re.IGNORECASE,
)


@dataclass
class TrackerOutput:
    welle: str = "25"
    df: str = "DF-148"
    iso_timestamp: str = ""
    source: str = "mock"
    cash_balance_eur: float = 0
    monthly_burn_eur: float = 0
    survival_months_baseline: float = 0
    survival_months_stressed: float = 0
    scenario_results: dict = field(default_factory=dict)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_stable(path, min_age_sec=300) -> bool:
    p = Path(path)
    if not p.exists():
        return False
    try:
        return (time.time() - p.stat().st_mtime) >= min_age_sec
    except OSError:
        return False


def _remove_lock_dir() -> None:
    if not LOCK_DIR.exists():
        return
    for child in LOCK_DIR.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink(missing_ok=True)
    LOCK_DIR.rmdir()


def acquire_lock_with_identity() -> bool:
    stale_after_sec = 6 * 60 * 60
    identity = {
        "df_id": DF_ID,
        "pid": os.getpid(),
        "created_at": iso_now(),
        "cwd": str(Path.cwd()),
    }

    try:
        LOCK_DIR.mkdir(mode=0o700)
        (LOCK_DIR / "identity.json").write_text(
            json.dumps(identity, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return True
    except FileExistsError:
        try:
            age = time.time() - LOCK_DIR.stat().st_mtime
            if age > stale_after_sec:
                _remove_lock_dir()
                LOCK_DIR.mkdir(mode=0o700)
                (LOCK_DIR / "identity.json").write_text(
                    json.dumps(identity, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                return True
        except OSError:
            return False
        return False
    except OSError:
        return False


def release_lock() -> None:
    try:
        identity_path = LOCK_DIR / "identity.json"
        owned = False
        if identity_path.exists():
            data = json.loads(identity_path.read_text(encoding="utf-8"))
            owned = data.get("pid") == os.getpid() and data.get("df_id") == DF_ID
        if owned:
            _remove_lock_dir()
    except OSError:
        pass
    except json.JSONDecodeError:
        pass


def k17_pre_action_verification(anchors) -> dict:
    missing = []
    for anchor in anchors:
        if anchor is None:
            missing.append("")
            continue
        if not Path(anchor).exists():
            missing.append(str(anchor))

    env_tag = os.getenv("DF_148_ENV_TAG", "local")
    return {
        "ok": len(missing) == 0,
        "missing_anchors": missing,
        "env_tag": env_tag,
    }


def _is_real_api_enabled() -> bool:
    return os.getenv("DF_148_REAL_API_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def scan_output_for_decision_keywords(text) -> list:
    if text is None:
        return []
    return sorted({match.group(0) for match in DECISION_KEYWORDS_REGEX.finditer(str(text))})


def assert_no_decision_keywords(output) -> None:
    text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
    hits = scan_output_for_decision_keywords(text)
    if hits:
        raise ValueError(f"Q_0/K_0 keyword block triggered: {', '.join(hits)}")


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def collect_tracker_output() -> TrackerOutput:
    real_api = _is_real_api_enabled()
    cash = _float_env("DF_148_CASH_BALANCE_EUR", 0.0)
    burn = _float_env("DF_148_MONTHLY_BURN_EUR", 0.0)

    baseline = cash / burn if burn > 0 else 0.0
    stressed_burn = burn * 1.25 if burn > 0 else 0.0
    stressed = cash / stressed_burn if stressed_burn > 0 else 0.0

    return TrackerOutput(
        iso_timestamp=iso_now(),
        source="real_api" if real_api else "mock",
        cash_balance_eur=round(cash, 2),
        monthly_burn_eur=round(burn, 2),
        survival_months_baseline=round(baseline, 4),
        survival_months_stressed=round(stressed, 4),
        scenario_results={
            "baseline": {
                "cash_balance_eur": round(cash, 2),
                "monthly_burn_eur": round(burn, 2),
                "survival_months": round(baseline, 4),
            },
            "stress_25pct_burn": {
                "cash_balance_eur": round(cash, 2),
                "monthly_burn_eur": round(stressed_burn, 2),
                "survival_months": round(stressed, 4),
            },
            "three_month_cash_survival": {
                "baseline_ge_3": baseline >= 3.0,
                "stressed_ge_3": stressed >= 3.0,
            },
        },
    )


def main() -> int:
    locked = acquire_lock_with_identity()
    if not locked:
        return 3

    try:
        pav = k17_pre_action_verification([DF_DIR])
        if not pav.get("ok"):
            return 3

        tracker = collect_tracker_output()
        payload = asdict(tracker)
        payload["k17_pre_action_verification"] = pav

        output_text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        assert_no_decision_keywords(output_text)

        report_dir = DF_DIR / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_path = report_dir / f"df-148-{date_tag}.json"
        report_path.write_text(output_text + "\n", encoding="utf-8")
        return 0
    except Exception as exc:
        sys.stderr.write(f"DF-148 failed: {exc}\n")
        return 3
    finally:
        release_lock()


if __name__ == "__main__":
    raise SystemExit(main())