#!/usr/bin/env bash
# kudaw-delivery: v1.8.0
# Level 1 of the contract's validation: does this repo expose the surface its profile
# requires?
#
# Usage:
#   scripts/contract-check.sh           Report, exit non-zero on any problem
#   scripts/contract-check.sh --warn    Report, always exit 0 (🟡 baseline mode)
#   scripts/contract-check.sh --facade  Only what the facade itself calls, through
#                                       delivery.mk alone — for adopt.sh, before the
#                                       repo's Makefile exists
#
# This is the check that a prose contract could never have: you cannot assert that a
# paragraph was followed, but you can assert that `make release` exists.
#
# A target that EXISTS is not a target that RUNS. `make -n` resolves the recipe without
# executing it, so a recipe that delegates to a script nobody wrote still resolves — and a
# freshly adopted repo used to get "OK" with four scripts missing, to find out on the first
# `make status` through a bare "No such file or directory". So the recipe `make -n` prints
# is also read: every scripts/*.sh it would call has to be there. Reading it, rather than
# keeping a list of what each profile owes, means the check cannot drift from delivery.mk.
#
# And a script that is there is not one a clean clone can run: with core.fileMode=false
# git records whatever mode it was first added with, usually 100644, and the working copy's
# +x says nothing about it. The mode is read from the index, which is what a clone gets.
#
# What it deliberately does NOT do is tell you whether the facade is up to date. It has no
# way to know the latest version — the plugin is not installed on a CI runner. It reports
# the seal it finds, and `/cicd audit` (which does have the plugin) compares.

set -euo pipefail

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
cd "$PROJECT_ROOT"

WARN_ONLY=0 FACADE_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --warn)   WARN_ONLY=1 ;;
        --facade) FACADE_ONLY=1 ;;
        *) echo "Usage: contract-check.sh [--warn] [--facade]" >&2; exit 2 ;;
    esac
done
MAKE=(make --no-print-directory)
(( FACADE_ONLY )) && MAKE+=(-f delivery.mk)

# Every profile owes these.
COMMON="help check status version baseline suggest-level bump set-version manifest
        changelog release-notes release contract-check self-test"
case "$PROFILE" in
    servicio)   EXTRA="image image-status promote-staging promote-prod" ;;
    libreria)   EXTRA="publish verify promote-main" ;;
    app-splunk) EXTRA="package verify promote-main" ;;
    *) echo "Error: unknown PROFILE '$PROFILE' in delivery.conf" >&2; exit 2 ;;
esac

failures=0
note() { printf '  %s %s\n' "$1" "$2"; }

echo "Contract check — profile: $PROFILE$( ((FACADE_ONLY)) && echo '  (facade only)')"
echo

# Scripts the recipes would call and that are not in the tree, with the target that
# calls them. A script called by several targets is reported once.
declare -A missing=()

(( FACADE_ONLY )) || echo "Targets:"
for t in $COMMON $EXTRA; do
    if ! recipe="$("${MAKE[@]}" -n "$t" 2>/dev/null)"; then
        # Under --facade the repo's own targets (the stages) are not in delivery.mk yet,
        # and that is the Makefile's job, which adopt.sh reports separately.
        (( FACADE_ONLY )) && continue
        note "✗" "$t  — required by the '$PROFILE' profile, not defined"
        failures=$((failures + 1))
        continue
    fi
    absent=()
    while IFS= read -r script; do
        [[ -z "$script" ]] && continue
        rel="${script#"$PROJECT_ROOT"/}"
        if [[ ! -f "$PROJECT_ROOT/$rel" ]]; then
            absent+=("$rel")
            missing[$rel]="${missing[$rel]:-$t}"
        fi
    # Path characters only: a recipe is shell, and `v=$(./scripts/version.sh get)` must
    # yield ./scripts/version.sh, not the substitution around it.
    done < <(grep -oE '[A-Za-z0-9_./-]*scripts/[A-Za-z0-9_./-]+\.sh' <<< "$recipe" | sort -u)
    # Under --facade the list below says it all, once per script.
    if (( FACADE_ONLY )); then
        :
    elif (( ${#absent[@]} )); then
        note "✗" "$t  — calls ${absent[*]}, which does not exist"
    else
        note "✓" "$t"
    fi
done

if (( ${#missing[@]} )); then
    failures=$((failures + ${#missing[@]}))
    (( FACADE_ONLY )) || echo
    echo "Scripts this repo owes (the '$PROFILE' profile does not ship them):"
    for rel in $(printf '%s\n' "${!missing[@]}" | sort); do
        note "✗" "$rel  (called by \`make ${missing[$rel]}\`)"
    done
    # For a library this is a decision, not a gap (2026-09-23): where a package goes —
    # which registries, in what order, with which credentials — had one instance to
    # measure, a monorepo shipping to four destinations, and one instance has no common
    # shape. Saying so keeps the ✗ from reading as "the contract forgot".
    if [[ "$PROFILE" == "libreria" ]]; then
        echo "     By design: the contract does not seal a library's artifact scripts, because"
        echo "     where a package goes is this repo's to say. Write them as thin wrappers"
        echo "     over whatever already publishes; comandos-proceso.md says what each reports."
    else
        echo "     WHAT the artifact is lives in them; references/comandos-proceso.md in"
        echo "     kudaw-tecnica/tech-cicd describes what each one has to report."
    fi
elif (( FACADE_ONLY )); then
    note "✓" "every script the facade calls is in the tree"
fi

# Executable bit, as the index records it. Only files with a shebang: _config.sh and the
# manifest flavours are sourced, and a mode they do not need is not a defect.
if git -C "$PROJECT_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    not_exec=() tracked=0
    while read -r mode _ _ path; do
        tracked=$((tracked + 1))
        [[ "$mode" == 100755 ]] && continue
        head -c2 "$path" 2>/dev/null | grep -q '^#!' && not_exec+=("$path")
    done < <(git ls-files -s -- 'scripts/*.sh')
    echo
    echo "Executable bit (as git records it):"
    if (( ${#not_exec[@]} )); then
        note "✗" "${#not_exec[@]} script(s) recorded 100644 — a clean clone gets 'permission denied':"
        printf '       %s\n' "${not_exec[@]}"
        echo "     Fix: git update-index --chmod=+x ${not_exec[*]}"
        failures=$((failures + 1))
    elif (( tracked == 0 )); then
        note "-" "no script is tracked yet; nothing to read the mode from"
    else
        note "✓" "every tracked script with a shebang is 100755"
    fi
fi

echo
echo "Facade seal:"
mapfile -t sealed < <(grep -rl '^# kudaw-delivery: v' delivery.mk scripts/ 2>/dev/null | sort)
if (( ${#sealed[@]} == 0 )); then
    note "✗" "no sealed files found — is the facade installed?"
    failures=$((failures + 1))
else
    mapfile -t versions < <(grep -h '^# kudaw-delivery: v' "${sealed[@]}" \
                            | sed 's/^# kudaw-delivery: //' | sort -u)
    if (( ${#versions[@]} == 1 )); then
        note "✓" "${#sealed[@]} file(s) at ${versions[0]}"
    else
        note "✗" "mixed versions across the facade: ${versions[*]} — a sync stopped halfway"
        failures=$((failures + 1))
    fi
fi

echo
if (( failures == 0 )); then
    echo "OK — the surface matches the contract."
    exit 0
fi
echo "$failures problem(s). The contract lives in kudaw-tecnica/tech-cicd,"
echo "references/comandos-proceso.md; \`/cicd audit\` explains how to close them."
(( WARN_ONLY )) && exit 0
exit 1
