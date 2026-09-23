---
name: cicd
description: >
  Run this repository's delivery process: the gates, the version bump, the
  changelog, packaging with AppInspect, and the release. Use it when the
  request is about moving a change towards main or publishing a version,
  however it is phrased — "release 2.0.0", "cut the release", "bump the
  version", "run the checks", "promote to main", "publish the apps", "is this
  ready to ship?", and the same in Spanish: "liberar 2.0.0", "hacer el
  release", "bumpear", "correr los checks", "promover a main", "publicar las
  apps", "está listo para liberar?". Do not use it to write app code, for SPL,
  or to run one integration scenario — that is tests/run.sh directly.
---

# cicd — delivery for nifi-monitoring-splunk

Profile **app-splunk**: the deliverable is a GitHub Release with both `.tar.gz`
attached. The facade (`Makefile` + `scripts/`, sealed by `tech-cicd`) does what
is deterministic; what lives here is judgement — when to stop, what to confirm,
how to present the evidence.

**Reimplement none of it.** If an order is not in the table, ask the facade:
`make help`, `make version`, `make baseline`, `make status`.

## What is particular to this repository

Three things that do not follow from the facade, and that decided how it was
set up:

1. **The version has one source and three derivations.** `make bump` writes
   `nifi_monitoring/default/app.conf` and stops there. The TA has no
   `app.conf` in the tree — ucc-gen generates it — so its `globalConfig.json`
   and `package/app.manifest` are rewritten from that one with
   **`make version-sync`**. Between the bump and the sync the tree is
   inconsistent and a unit test says so: that is correct, not a problem.
   **Never edit a version by hand in the TA's files.**

2. **The TA is not installable from the tree.** `make build` generates it into
   `output/`. Packaging `nifi_TA_monitoring/` directly produces an add-on with
   no `app.conf` and no UI, and `slim` will not complain.

3. **This repository does not use Conventional Commits.** `make suggest-level`
   will say `patch` almost every time, and `make changelog` will file
   everything under "📦 Other". **Trust neither**: propose the level by reading
   the commits yourself, and write the CHANGELOG entry by hand. The 2.0.0 one
   was written that way, and says so at the top.

## Orders

| Request | What runs | What you confirm first |
|---|---|---|
| `check` | `make check` | nothing; it is read-only |
| `bump [level]` | `make bump LEVEL=<level>`, then **`make version-sync`** | the level, always — `suggest-level` is not reliable here |
| `changelog` | edit `CHANGELOG.md` by hand; `make changelog NO_COMMIT=1` only if you want the scaffold | the wording of the entry |
| `package` | `make package` | nothing |
| `validate` | `make validate` | nothing |
| `promote` | `make promote-main` | **yes, always**: it merges to `main` and pushes |
| `release` | `make release` | **yes, always**: it creates the tag and the GitHub Release |
| `status` | `make status` | nothing |
| `audit` | `adopt.sh <repo> --check`, from the `tech-cicd` plugin | nothing |

## The sequence

```
check → bump → version-sync → changelog → validate → promote → release
```

Before starting, check three things the facade does not look at:

- The tree is clean and you are on the working branch, not on `main`.
- `make status` reports no drift you cannot explain.
- For a release: **the integration matrix has run.** `make check` runs the unit
  tests and AppInspect, not the ten scenarios. Those are
  `cd tests && ./run.sh <profile>` or the `integration` job of `main.yml`.

## How to present the evidence

- After `check`, show the AppInspect summary for **both apps** with their
  numbers (`error`, `failure`, `warning`), not a "passed". The gate is 13
  warnings and today they are 5 and 12: a number that goes up is worth looking
  at even when it still passes.
- After `bump`, show the old version and the new one, and **confirm that
  `version-sync` ran** — it is the step people forget.
- Before `promote` and before `release`, say in one line what is about to
  happen and wait for the yes. Both are irreversible in practice: a push to
  `main` and a public tag.
- When something fails, show the target's raw output. Do not summarise it: the
  facade's message says what to do.

## When something does not fit

Do not edit `delivery.mk` or `scripts/` — they are sealed. Either it is a value
that belongs in `delivery.conf`, or it is a change the `tech-cicd` contract
should absorb for every repository. **One is open today**: the `app-conf`
flavour writes a single manifest, and this repository needs three files
touched. `version-sync` covers it from this side, but the contract has no
notion of a manifest spread across files.
