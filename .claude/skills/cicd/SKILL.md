---
name: cicd
description: >
  Run this repository's delivery process, as a subcommand: `cicd check`,
  `cicd status`, `cicd bump [patch|minor|major]`, `cicd changelog`,
  `cicd package`, `cicd validate`, `cicd promote`, `cicd release`.
  Without a subcommand, report the state and say what is next. Also use it
  when a request means one of those without naming it — shipping a version,
  moving a change towards main, or asking whether it is ready. Not for
  writing app code, not for SPL, and not for running one integration
  scenario, which is tests/run.sh directly.
---

# cicd

The deliverable is a GitHub Release with both packaged apps attached. `make`
does the work; this covers the order, what to confirm, and how to report it.

Do not reimplement any target. If something is not here, ask: `make help`,
`make status`, `make version`.

## Subcommands

| Subcommand | Runs | Confirm first |
|---|---|---|
| `check` | `make check` | nothing; read-only |
| `status` | `make status` | nothing |
| `bump [level]` | `make bump LEVEL=<level>`, then `make version-sync` | the level, always |
| `changelog` | edit `CHANGELOG.md`, then `make changelog NO_COMMIT=1` if you want the scaffold | the wording |
| `package` | `make package` | nothing |
| `validate` | `make validate` | nothing |
| `promote` | `make promote-main` | **yes**: merges to `main` and pushes |
| `release` | `make release` | **yes**: creates the tag and the release |

## Sequence

```
check → bump → version-sync → changelog → validate → promote → release
```

## Three things to get right

1. **`bump` is not finished until `version-sync` runs.** `bump` writes one
   file; the add-on's version is derived from it and has to be rewritten.
   Between the two the tree is inconsistent and a unit test fails, which is
   the intended warning. Never edit a version by hand.

2. **The add-on is generated.** `make build` produces it; packaging the source
   directory yields something that installs and does nothing, and the
   packaging tool does not complain. `make validate` checks for this.

3. **Commit subjects here are not Conventional Commits.** `make suggest-level`
   and the changelog generator will misclassify almost everything. Choose the
   level by reading the commits, and write the changelog entry by hand.

## Before a release

- Clean tree, on a working branch, not on `main`.
- `make status` shows no drift you cannot explain.
- The integration matrix has run. `make check` covers the unit tests and the
  package validation, not the ten scenarios — those are
  `cd tests && ./run.sh <profile>`.

## Reporting

- After `check` or `validate`, give the validator's counts for **both** apps,
  not a "passed". A warning count that rose is worth a look even when it still
  passes the gate.
- After `bump`, show the old and new version and say that `version-sync` ran.
- Before `promote` and `release`, state in one line what is about to happen
  and wait for a yes. Both are irreversible.
- On failure, show the raw output. The message says what to do.
