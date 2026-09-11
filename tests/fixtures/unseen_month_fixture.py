"""Test fixture generator for unseen-month live operational rehearsal.

Simulates an unseen operating period (e.g. April 2026) with:
1. A brand new gateway ID never seen during initial model training.
2. An established gateway that goes completely silent in the live month (silent in recent 7 days).
3. Canonical schema/layout matching the frozen telemetry contract.
4. Sufficient eligible telemetry-backed gateways to support top-15 scoring.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import pandas as pd


def create_unseen_month_dataset(
    target_dir: pathlib.Path,
    week_str: str = "2026-04-06",
) -> pathlib.Path:
    """Create an isolated, fully valid unseen-month dataset directory."""
    target_dir.mkdir(parents=True, exist_ok=True)
    monday = dt.date.fromisoformat(week_str)

    # 1. Gateway Master
    # - AA0000000001: brand new unseen gateway (installed 2026-01-15)
    # - 0639EA000002: established gateway that went recently silent (installed 2025-01-01)
    # - 0639EA000003 .. 0639EA000018: 16 normal gateways (installed 2025-01-01)
    # Total = 18 eligible gateways (>= 15 required for top-15 scoring)
    master_rows = [
        {
            "gateway_id": "AA0000000001",
            "tenant": "TENANT_UNSEEN",
            "site_type": "Außenmast",
            "region": "NORTH",
            "hw_model": "V1",
            "antenna_type": "OMNI",
            "fw_version": "1.0.0",
            "installed_on": "2026-01-15",
            "decommissioned_on": "",
            "n_meters_installed": 10,
        },
        {
            "gateway_id": "0639EA000002",
            "tenant": "TENANT_A",
            "site_type": "Gebäude",
            "region": "SOUTH",
            "hw_model": "V1",
            "antenna_type": "OMNI",
            "fw_version": "1.0.0",
            "installed_on": "2025-01-01",
            "decommissioned_on": "",
            "n_meters_installed": 12,
        },
    ]

    for idx in range(3, 19):
        gid = f"0639EA{idx:06X}"
        master_rows.append({
            "gateway_id": gid,
            "tenant": "TENANT_B" if idx % 2 == 0 else "TENANT_C",
            "site_type": "Gebäude",
            "region": "CENTRAL",
            "hw_model": "V1",
            "antenna_type": "DIRECTIONAL",
            "fw_version": "1.0.0",
            "installed_on": "2025-01-01",
            "decommissioned_on": "",
            "n_meters_installed": 8,
        })

    master_df = pd.DataFrame(master_rows)
    master_path = target_dir / "gateway_master.csv"
    master_df.to_csv(master_path, index=False, encoding="cp1252")

    # 2. Telemetry Parquet
    cutoff_utc = dt.datetime(monday.year, monday.month, monday.day, 0, 0, 0, tzinfo=dt.timezone.utc)
    baseline_days = 28
    start_utc = cutoff_utc - dt.timedelta(days=baseline_days)
    silent_cutoff_utc = cutoff_utc - dt.timedelta(days=7)

    total_hours = baseline_days * 24  # 672 hours

    telemetry_records = []

    # AA0000000001 (unseen) has full 28 days of data
    # 0639EA000003 .. 0639EA000018 have full 28 days of data
    # 0639EA000002 (silent) has data up to silent_cutoff_utc (first 21 days), then 0 rows in trailing 7 days
    for h in range(total_hours):
        ts = start_utc + dt.timedelta(hours=h)
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Unseen gateway
        telemetry_records.append({
            "gateway_id": "AA0000000001",
            "ts_utc": ts_str,
            "offline_duration_sec": 120.0 if h % 24 == 0 else 0.0,
            "disconnection_cnt": 1.0 if h % 24 == 0 else 0.0,
            "reboot_cnt": 0.0,
        })

        # Recently silent gateway (only before silent_cutoff_utc)
        if ts < silent_cutoff_utc:
            telemetry_records.append({
                "gateway_id": "0639EA000002",
                "ts_utc": ts_str,
                "offline_duration_sec": 0.0,
                "disconnection_cnt": 0.0,
                "reboot_cnt": 0.0,
            })

        # Other 16 gateways
        for idx in range(3, 19):
            gid = f"0639EA{idx:06X}"
            # Inject slight signal variation so scores are distinct
            off_sec = float((idx * 15 + h) % 300) if h % 48 == 0 else 0.0
            disc = 1.0 if (h % 36 == 0 and idx % 3 == 0) else 0.0
            telemetry_records.append({
                "gateway_id": gid,
                "ts_utc": ts_str,
                "offline_duration_sec": off_sec,
                "disconnection_cnt": disc,
                "reboot_cnt": 0.0,
            })

    tel_df = pd.DataFrame(telemetry_records)
    tel_dir = target_dir / "telemetry"
    tel_dir.mkdir(parents=True, exist_ok=True)
    tel_df.to_parquet(tel_dir / "part-0000.parquet", index=False)

    return target_dir
