#!/usr/bin/env bash
# kudaw-delivery: v1.3.0
# Promote code between environment branches: develop -> testing -> main.
#
# Usage:
#   scripts/promote.sh staging     Merge develop into testing and push
#   scripts/promote.sh prod        Merge testing into main and push
#   scripts/promote.sh main        Merge develop into main and push (library profile)
#
# A library has no staging environment to deploy to: what plays that role is `verify`,
# which confirms the artifact is live in its registry before main advances. So it
# promotes develop -> main directly, and the rule that only verified code reaches main
# still holds.
#
# Pushing to testing/main is what triggers the deploy on the hosting platform,
# so this is the irreversible step. The caller is responsible for confirming
# with the user first; this script only refuses states that cannot be right.
#
# Whatever happens, it returns to the branch you started on — including on a
# failed merge, so a conflict never strands you on testing or main.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

TARGET="${1:-}"
case "$TARGET" in
    staging) FROM="develop"; TO="testing" ;;
    prod)    FROM="testing"; TO="main" ;;
    main)    FROM="develop"; TO="main" ;;
    *) echo "Usage: scripts/promote.sh [staging|prod|main]" >&2; exit 2 ;;
esac

ORIGINAL_BRANCH="$(git branch --show-current)"
restore_branch() {
    local current
    current="$(git branch --show-current)"
    if [[ -n "$ORIGINAL_BRANCH" && "$current" != "$ORIGINAL_BRANCH" ]]; then
        echo "Returning to '$ORIGINAL_BRANCH'..."
        git checkout "$ORIGINAL_BRANCH" >/dev/null 2>&1 \
            || echo "Warning: could not return to '$ORIGINAL_BRANCH'; you are on '$current'" >&2
    fi
}
trap restore_branch EXIT

# --- preconditions ------------------------------------------------------------

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Error: working tree is not clean. Uncommitted changes:" >&2
    git status --short >&2
    exit 1
fi

# staging promotes what is on develop, so that has to be where we are. prod
# promotes what is on testing, which does not require being checked out.
if [[ "$FROM" == "develop" && "$ORIGINAL_BRANCH" != "develop" ]]; then
    echo "Error: 'promote $TARGET' must run from 'develop' (currently on '$ORIGINAL_BRANCH')" >&2
    exit 1
fi

echo "Fetching origin..."
git fetch origin --quiet

if ! git rev-parse -q --verify "refs/remotes/origin/$FROM" >/dev/null; then
    echo "Error: origin/$FROM does not exist" >&2
    exit 1
fi

# Nothing to promote is not a failure, but it is not a promotion either.
if [[ -n "$(git rev-parse -q --verify "refs/remotes/origin/$TO" || true)" ]]; then
    pending="$(git rev-list --count "origin/$TO..origin/$FROM")"
    if [[ "$pending" == "0" ]]; then
        echo "Nothing to promote: origin/$TO already has everything on origin/$FROM."
        exit 0
    fi
    echo "Promoting $pending commit(s) from $FROM to $TO."
fi

# For staging, local develop is the thing being promoted — it must be pushed,
# or testing would get a state nobody else can see.
if [[ "$TARGET" == "staging" ]]; then
    unpushed="$(git rev-list --count "origin/develop..develop")"
    if [[ "$unpushed" != "0" ]]; then
        echo "Error: develop has $unpushed unpushed commit(s). Push them first." >&2
        exit 1
    fi
fi

# --- promote ------------------------------------------------------------------

echo "Checking out $TO..."
git checkout "$TO"
git pull --ff-only origin "$TO"

echo "Merging $FROM into $TO..."
git merge --no-ff "$FROM" -m "chore: promote $FROM to $TO"

echo "Pushing $TO..."
git push origin "$TO"

echo
echo "Done: origin/$TO now includes $FROM."
echo "The push triggers the deploy on the configured platform."
