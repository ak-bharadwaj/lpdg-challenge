@echo off
set PYTHON=python
set OP_DATA=--data ./data
if not "%LIVE_DATA%"=="" set OP_DATA=--data %LIVE_DATA%
set OP_WEEK=
if not "%LIVE_WEEK%"=="" set OP_WEEK=--week %LIVE_WEEK%
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
) else if "%1"=="ops-status" (
    %PYTHON% scripts/ops.py status
) else if "%1"=="ops-preflight" (
    %PYTHON% scripts/ops.py preflight %OP_DATA% %OP_WEEK%
) else if "%1"=="ops-live" (
    %PYTHON% scripts/ops.py run-live %OP_DATA% %OP_WEEK%
) else if "%1"=="ops-evaluate" (
    %PYTHON% scripts/ops.py evaluate --candidate v0002 %OP_DATA%
) else if "%1"=="ops-promote" (
    %PYTHON% scripts/ops.py promote --candidate v_promotable %OP_DATA% %OP_WEEK% --yes
) else if "%1"=="ops-rollback" (
    %PYTHON% scripts/ops.py rollback --to v0001 %OP_DATA% %OP_WEEK%
) else if "%1"=="ops-verify" (
    %PYTHON% scripts/ops.py verify %OP_DATA% %OP_WEEK% --version v0001
) else if "%1"=="ops-demo" (
    %PYTHON% scripts/ops.py demo %OP_DATA% %OP_WEEK%
) else if "%1"=="ops-snapshot" (
    %PYTHON% scripts/ops.py status --export registry_certified_baseline.json
) else if "%1"=="ops-restore" (
    %PYTHON% scripts/ops.py restore-snapshot --from registry_certified_baseline.json
) else if "%1"=="ops-change" (
    if "%2"=="" (
        %PYTHON% scripts/ops.py change --candidate v0002 %OP_DATA% %OP_WEEK% --yes
    ) else if /i "%2"=="CANDIDATE" (
        %PYTHON% scripts/ops.py change --candidate %3 %OP_DATA% %OP_WEEK% --yes
    ) else (
        %PYTHON% scripts/ops.py change --candidate %2 %OP_DATA% %OP_WEEK% --yes
    )
) else if "%1"=="ops-rollback-to" (
    if "%2"=="" (
        %PYTHON% scripts/ops.py rollback-to --version v0001 %OP_DATA% %OP_WEEK%
    ) else if /i "%2"=="VERSION" (
        %PYTHON% scripts/ops.py rollback-to --version %3 %OP_DATA% %OP_WEEK%
    ) else if /i "%2"=="TARGET" (
        %PYTHON% scripts/ops.py rollback-to --version %3 %OP_DATA% %OP_WEEK%
    ) else (
        %PYTHON% scripts/ops.py rollback-to --version %2 %OP_DATA% %OP_WEEK%
    )
) else (
    %PYTHON% scripts/make_submission.py --data ./data
)

