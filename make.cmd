@echo off
set PYTHON=python
set OP_DATA=--data ./data
if not "%LIVE_DATA%"=="" set OP_DATA=--data %LIVE_DATA%
set OP_WEEK=
if not "%LIVE_WEEK%"=="" set OP_WEEK=--week %LIVE_WEEK%
set OP_OUTPUT=--output predictions_week.csv
if not "%LIVE_OUTPUT%"=="" set OP_OUTPUT=--output %LIVE_OUTPUT%
if "%1"=="help" (
    echo Available commands:
    echo   make run              - Reviewer P0 entry point: verify data contracts and gateway eligibility foundation
    echo   make train            - Construct and evaluate candidate model v0002
    echo   make predict          - Run predictions for active model
    echo   make promote          - Run frozen promotion gate evaluation
    echo   make rollback         - Reversible atomic rollback demonstration
    echo   make test             - Run test suite
    echo   make drift            - Run structural schema drift check
    echo   make ops-status       - Read-only operator status summary
    echo   make ops-preflight    - Read-only preflight safety and contract check
    echo   make ops-live         - Execute live prediction for operator week
    echo   make ops-predictions - Display and strictly validate live predictions artifact
    echo   make ops-evaluate     - Candidate evaluation against promotion gate
    echo   make ops-promote      - Atomically promote candidate model
    echo   make ops-rollback     - Reversible atomic rollback
    echo   make ops-verify       - Read-only explicit-version replay verification
    echo   make ops-demo         - Orchestrated live session demonstration
    echo   make ops-snapshot     - Export read-only certified baseline registry snapshot
    echo   make ops-restore      - Safely restore registry state from exported snapshot
    echo   make ops-change       - Live evaluator model change through authoritative gate ^(CANDIDATE=...^)
    echo   make ops-rollback-to  - Live evaluator atomic rollback to target version ^(VERSION=...^)
) else if "%1"=="run" (
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
    %PYTHON% scripts/ops.py preflight %OP_DATA% %OP_WEEK%
) else if "%1"=="ops-live" (
    %PYTHON% scripts/ops.py run-live %OP_DATA% %OP_WEEK% %OP_OUTPUT%
) else if "%1"=="ops-predictions" (
    %PYTHON% scripts/ops.py show-predictions %OP_OUTPUT% %OP_WEEK%
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

