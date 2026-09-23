---
name: cicd
description: >
  Run this repository's delivery process, as a subcommand: `cicd check`,
  `cicd status`, `cicd bump [patch|minor|major]`, `cicd changelog`,
  `cicd package`, `cicd verify`, `cicd validate`, `cicd promote`,
  `cicd release`.
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
| `check` | `make check` | nothing; read-only, but it takes ~20 min |
| `status` | `make status` | nothing |
| `bump [level]` | `make bump LEVEL=<level>` (runs `version-sync` itself) | the level, always |
| `changelog` | edit `CHANGELOG.md`, then `make changelog NO_COMMIT=1` if you want the scaffold | the wording |
| `package` | `make package`, then `make package DRY_RUN=0` | nothing; needs a clean tree |
| `verify` | `make verify` | nothing |
| `validate` | `make validate` | nothing |
| `promote` | `make promote-main` | **yes**: merges to `main` and pushes |
| `release` | `make release` | **yes**: creates the tag and the release |

## Sequence

```
check → bump → changelog → package → verify → promote → release
```

## Three things to get right

1. **`bump` runs `version-sync` itself** (`POST_BUMP` in `delivery.conf`).
   `bump` writes one file and the add-on's version is derived from it; if the
   sync fails, the bump fails and says the tree is inconsistent, and a unit
   test fails too. Do not run the sync by hand after a bump that succeeded,
   and never edit a version by hand.

2. **The add-on is generated.** `make build` produces it; packaging the source
   directory yields something that installs and does nothing, and the
   packaging tool does not complain. `make package` runs the build first and
   packages from `output/`; `make verify` then checks that the version
   **inside** both packages is the manifest's. `make validate` is the same
   gate for `check`, on the working tree; its packages never reach a release.

3. **Commit subjects here are not Conventional Commits.** `make suggest-level`
   and the changelog generator will misclassify almost everything. Choose the
   level by reading the commits, and write the changelog entry by hand.

## Before a release

- Clean tree, on a working branch, not on `main`.
- `make status` shows no drift you cannot explain.
- `make check PROFILES=release` has run, not just `make check`. The default
  runs four scenarios — one per version line, per architecture and per
  strategy; a release wants all ten.

`check` runs the integration scenarios as well as the unit tests and the
package validation, which is why it takes twenty minutes rather than four.
For the edit loop call a stage directly: `make lint`, `make test`.

## Reporting

- After `check`, `validate` or `package`, give the validator's counts for **both** apps,
  not a "passed". After `check`, give the per-scenario line too. A warning count that rose is worth a look even when it still
  passes the gate.
- After `bump`, show the old and new version and say that `version-sync` ran.
- Before `promote` and `release`, state in one line what is about to happen
  and wait for a yes. Both are irreversible.
- On failure, show the raw output. The message says what to do.
