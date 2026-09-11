# RESQ-MLOps Canonical Makefile

PYTHON ?= python

.PHONY: help run train predict promote rollback test drift clean frontend ops-status ops-preflight ops-live ops-evaluate ops-promote ops-rollback ops-verify ops-demo

LIVE_DATA ?= ./data
LIVE_WEEK ?=
CANDIDATE ?= v0002
TARGET ?=

help:
	@echo "Available commands:"
	@echo "  make run           - Reviewer P0 entry point: verify data contracts and gateway eligibility foundation"
	@echo "  make train         - Construct and evaluate candidate model v0002"
	@echo "  make predict       - Run predictions for active model"
	@echo "  make promote       - Run frozen promotion gate evaluation"
	@echo "  make rollback      - Reversible atomic rollback demonstration"
	@echo "  make test          - Run test suite"
	@echo "  make drift         - Run structural schema drift check"
	@echo "  make frontend      - Launch RESQ Operations Console web dashboard"
	@echo "  make ops-status    - Read-only operator status summary"
	@echo "  make ops-preflight - Read-only preflight safety and contract check"
	@echo "  make ops-live      - Execute live prediction for operator week"
	@echo "  make ops-evaluate  - Candidate evaluation against promotion gate"
	@echo "  make ops-promote   - Atomically promote candidate model"
	@echo "  make ops-rollback  - Reversible atomic rollback"
	@echo "  make ops-verify    - Read-only explicit-version replay verification"
	@echo "  make ops-demo      - Orchestrated 8-step live session demonstration"

run:
	$(PYTHON) scripts/make_submission.py --data ./data

train:
	$(PYTHON) scripts/train.py --data ./data --candidate v0002

predict:
	$(PYTHON) scripts/predict.py --data ./data

promote:
	$(PYTHON) scripts/promote.py --candidate v0002

rollback:
	$(PYTHON) scripts/rollback.py

test:
	$(PYTHON) -m pytest tests/

drift:
	$(PYTHON) scripts/check_drift.py --data ./data

frontend:
	$(PYTHON) frontend/server.py --port 8080

ops-status:
	$(PYTHON) scripts/ops.py status

ops-preflight:
	$(PYTHON) scripts/ops.py preflight --data $(LIVE_DATA) $(if $(LIVE_WEEK),--week $(LIVE_WEEK),)

ops-live:
	$(PYTHON) scripts/ops.py run-live --data $(LIVE_DATA) $(if $(LIVE_WEEK),--week $(LIVE_WEEK),)

ops-evaluate:
	$(PYTHON) scripts/ops.py evaluate --candidate $(CANDIDATE) --data $(LIVE_DATA)

ops-promote:
	$(PYTHON) scripts/ops.py promote --candidate $(CANDIDATE) --data $(LIVE_DATA) $(if $(LIVE_WEEK),--week $(LIVE_WEEK),) --yes

ops-rollback:
	$(PYTHON) scripts/ops.py rollback $(if $(TARGET),--to $(TARGET),) --data $(LIVE_DATA) $(if $(LIVE_WEEK),--week $(LIVE_WEEK),)

ops-verify:
	$(PYTHON) scripts/ops.py verify --data $(LIVE_DATA) $(if $(LIVE_WEEK),--week $(LIVE_WEEK),) $(if $(TARGET),--version $(TARGET),$(if $(VERSION),--version $(VERSION),))

ops-demo:
	$(PYTHON) scripts/ops.py demo --data $(LIVE_DATA) $(if $(LIVE_WEEK),--week $(LIVE_WEEK),)


