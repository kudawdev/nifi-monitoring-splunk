# Delivery facade (sealed, from tech-cicd) plus this repo's stages.
#
# `make help` lists everything. The stages below are the part that is ours:
# what lint, test and security mean for two Splunk apps, and how they are
# built, packaged and validated.
#
# Everything runs inside kudaw/appinspect:latest, the image CI uses, so the
# slim and AppInspect versions here are the ones that gate the release. The
# only local prerequisites are Docker and Python 3.

include delivery.mk

DELIVERY_TASKS_HINT := make build / package / validate; the harness is tests/run.sh

SHELL := /bin/bash
REPO  := $(shell pwd)
APP   := nifi_monitoring
TA    := nifi_TA_monitoring

# CI's gate, measured per app: 5 for the app, 12 for the TA. A unit test fails
# if this and the workflows' MAX_WARNING disagree.
MAX_WARNING ?= 13

IMAGE := kudaw/appinspect:latest
# HOME must be writable: slim creates ~/.config on first run and the image's
# default HOME is not writable by the invoking uid.
DOCKER := docker run --rm -u "$(shell id -u):$(shell id -g)" -e HOME=/w \
          -v "$(REPO):/w" -w /w $(IMAGE)

.PHONY: lint test security check build version-sync package validate clean

## --- stages -----------------------------------------------------------

lint: ## Shell and Python syntax across the harness and the add-on
	@echo "==> lint"
	@find . -name '*.sh' -not -path './output/*' -not -path './.venv*' \
	    -not -path './.git/*' -print0 | xargs -0 -n1 bash -n
	@find nifi_TA_monitoring tests -name '*.py' -not -path '*/output/*' \
	    -print0 | xargs -0 -n1 python3 -m py_compile
	@echo "    ok"

test: build ## The unit suite, against the built add-on
	@echo "==> test"
	@cd tests/unit && REQUIRE_BUILT_TA=1 python3 -m unittest discover

security: validate ## AppInspect precert is the security gate for a Splunk app
	@echo "==> security: covered by validate (AppInspect precert)"

check: ## Every gate, in one pass, without stopping at the first failure
	@failed=0; \
	$(MAKE) --no-print-directory lint    || failed=1; \
	$(MAKE) --no-print-directory test    || failed=1; \
	$(MAKE) --no-print-directory validate|| failed=1; \
	if [ $$failed -ne 0 ]; then echo "==> check FAILED"; exit 1; fi; \
	echo "==> check passed"

## --- build and package ------------------------------------------------

build: ## Generate the TA into output/ (the app needs no generation)
	@./tests/build-ta.sh

version-sync: ## Rewrite the TA's globalConfig and manifest from app.conf
	@python3 $(TA)/gen_globalconfig.py

package: build ## The two .tar.gz a release attaches
	@echo "==> packaging $$(./scripts/version.sh get)"
	@$(DOCKER) sh -c 'slim package $(APP) && slim package output/$(TA)'
	@ls -l $(APP)-$$(./scripts/version.sh get).tar.gz \
	       $(TA)-$$(./scripts/version.sh get).tar.gz

validate: package ## slim validate + AppInspect precert, with CI's gate
	@v=$$(./scripts/version.sh get); \
	for app in $(APP) $(TA); do \
	  echo "==> $$app"; \
	  $(DOCKER) sh -c "slim validate $$app-$$v.tar.gz" || exit 1; \
	  $(DOCKER) sh -c "splunk-appinspect inspect $$app-$$v.tar.gz \
	      --output-file $$app-appinspect.json --mode precert >/dev/null" || exit 1; \
	  python3 -c "import json,sys; \
s=json.load(open('$$app-appinspect.json'))['summary']; print('   ', s); \
sys.exit(1) if s['error'] or s['failure'] or s['warning'] > $(MAX_WARNING) else None" \
	    || { echo "    FAILED the gate (max $(MAX_WARNING) warnings)"; exit 1; }; \
	done
	@echo "==> both apps pass the gate"

clean: ## Remove output/, the packages and what slim leaves behind
	@rm -rf output *.tar.gz *-appinspect.json .config $(APP)/app.manifest
	@echo "==> cleaned"
