@echo off
set PYTHON=python
if "%1"=="run" (
    %PYTHON% scripts/make_submission.py --data ./data
) else if "%1"=="train" (
    %PYTHON% scripts/train.py --data ./data --candidate v0002
) else if "%1"=="predict" (
    %PYTHON% scripts/predict.py --data ./data
) else if "%1"=="promote" (
    %PYTHON% scripts/promote.py --candidate v0002
) else if "%1"=="rollback" (
    %PYTHON% scripts/rollback.py
) else if "%1"=="test" (
    %PYTHON% -m pytest tests/
) else if "%1"=="drift" (
    %PYTHON% scripts/check_drift.py --data ./data
) else if "%1"=="frontend" (
    %PYTHON% frontend/server.py --port 8080
) else if "%1"=="ops-status" (
    %PYTHON% scripts/ops.py status
) else if "%1"=="ops-preflight" (
    %PYTHON% scripts/ops.py preflight --data ./data
) else if "%1"=="ops-live" (
    %PYTHON% scripts/ops.py run-live --data ./data --week 2026-02-02
) else if "%1"=="ops-evaluate" (
    %PYTHON% scripts/ops.py evaluate --candidate v0002 --data ./data
) else if "%1"=="ops-promote" (
    %PYTHON% scripts/ops.py promote --candidate v_promotable --data ./data --yes
) else if "%1"=="ops-rollback" (
    %PYTHON% scripts/ops.py rollback --to v0001 --data ./data --week 2026-02-02
) else if "%1"=="ops-verify" (
    %PYTHON% scripts/ops.py verify --data ./data --week 2026-02-02 --version v0001
) else if "%1"=="ops-demo" (
    %PYTHON% scripts/ops.py demo --data ./data --week 2026-02-02
) else if "%1"=="ops-snapshot" (
    %PYTHON% scripts/ops.py status --export registry_certified_baseline.json
) else if "%1"=="ops-restore" (
    %PYTHON% scripts/ops.py restore-snapshot --from registry_certified_baseline.json
) else if "%1"=="ops-change" (
    if "%2"=="" (
        %PYTHON% scripts/ops.py change --candidate v0002 --data ./data --yes
    ) else (
        %PYTHON% scripts/ops.py change --candidate %2 --data ./data --yes
    )
) else if "%1"=="ops-rollback-to" (
    if "%2"=="" (
        %PYTHON% scripts/ops.py rollback-to --version v0001 --data ./data --week 2026-02-02
    ) else (
        %PYTHON% scripts/ops.py rollback-to --version %2 --data ./data --week 2026-02-02
    )
) else (
    %PYTHON% scripts/make_submission.py --data ./data
)

