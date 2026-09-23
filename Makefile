# Local build, packaging and validation.
#
# The same three steps CI runs, callable by a person. They used to be a Docker
# one-liner pasted into the README, tests/README.md and the output of
# `run.sh --bare`, which is three copies free to drift from the workflow that
# actually ships the apps.
#
# Everything runs inside kudaw/appinspect:latest, the image CI uses, so the
# slim and AppInspect versions here are the ones that gate the release. The
# only local prerequisites are Docker and Python 3.
#
#   make            # what each target does
#   make build      # generate the TA into output/
#   make package    # build, then the two .tar.gz a release attaches
#   make validate   # package, then slim validate + AppInspect precert
#   make test       # the unit suite, against the built add-on
#   make clean      # drop output/ and the packages

SHELL := /bin/bash
REPO  := $(shell pwd)
APP   := nifi_monitoring
TA    := nifi_TA_monitoring

# Read from the app the workflow reads it from, not declared here: a version in
# a Makefile is a second source of truth that nothing checks.
VERSION := $(shell grep -m1 '^version' $(APP)/default/app.conf | tr -d ' ' | cut -d= -f2)

# CI's gate. Measured per app: 5 for the app, 12 for the TA.
MAX_WARNING ?= 13

IMAGE := kudaw/appinspect:latest
# HOME must be writable: slim creates ~/.config on first run, and the image's
# default HOME is not writable by the invoking uid.
DOCKER := docker run --rm -u "$(shell id -u):$(shell id -g)" -e HOME=/w \
          -v "$(REPO):/w" -w /w $(IMAGE)

.DEFAULT_GOAL := help
.PHONY: help build package validate test clean

help: ## Show this help
	@echo "Building $(APP) and $(TA) $(VERSION)"
	@echo
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*## "}{printf "  \033[1m%-10s\033[0m %s\n", $$1, $$2}'

build: ## Generate the TA into output/ (the app needs no generation)
	@./tests/build-ta.sh

package: build ## Build the two .tar.gz a release attaches
	@echo "==> packaging $(VERSION)"
	@$(DOCKER) sh -c 'slim package $(APP) && slim package output/$(TA)'
	@ls -l $(APP)-$(VERSION).tar.gz $(TA)-$(VERSION).tar.gz

validate: package ## slim validate + AppInspect precert, with CI's gate
	@for app in $(APP) $(TA); do \
	  echo "==> $$app"; \
	  $(DOCKER) sh -c "slim validate $$app-$(VERSION).tar.gz" || exit 1; \
	  $(DOCKER) sh -c "splunk-appinspect inspect $$app-$(VERSION).tar.gz \
	      --output-file $$app-appinspect.json --mode precert >/dev/null" || exit 1; \
	  python3 -c "import json,sys; \
s=json.load(open('$$app-appinspect.json'))['summary']; print('   ', s); \
sys.exit(1) if s['error'] or s['failure'] or s['warning'] > $(MAX_WARNING) else None" \
	    || { echo "    FAILED the gate (max $(MAX_WARNING) warnings)"; exit 1; }; \
	done
	@echo "==> both apps pass the gate"

test: build ## Run the unit suite against the built add-on
	@cd tests/unit && REQUIRE_BUILT_TA=1 python3 -m unittest discover

clean: ## Remove output/, the packages and what slim leaves behind
	@rm -rf output *.tar.gz *-appinspect.json .config $(APP)/app.manifest
	@echo "==> cleaned"
