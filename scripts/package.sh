#!/usr/bin/env bash
# kudaw-delivery: v1.8.0
# Build the versioned artifacts of a Splunk app: dist/<app>-<version>.tar.gz, one per app
# the repo ships (see _app.sh for APP_DIRS).
#
# The slot is `package`, not `publish`, because for a Splunk app this publishes nothing:
# it produces the artifacts and puts each one through the gate. What publishes is
# `release`, which attaches them to the GitHub Release. Calling it `publish` would mean the
# same command uploads for a library and only builds here — the divergence the canonical
# names exist to prevent.
#
#   package.sh --dry-run    say what it would build, without building
#   package.sh              the release artifacts: clean tree + full gate
#   package.sh --dev        dev builds to install and try
#
# The Makefile is what makes dry-run the default for a human: `make package` adds
# --dry-run, and DRY_RUN=0 is what takes it away.
#
# --dev exists because the release path deliberately refuses a dirty tree — an artifact
# has to correspond to a commit — and that leaves "build me something I can install and
# try" uncovered. It is the counterpart of SUFFIX in the servicio profile.
set -euo pipefail

NEEDS_MANIFEST=1
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_app.sh"
cd "$PROJECT_ROOT"

MODE="dry-run"
# No argument means the release build, because that is what the Makefile passes for
# DRY_RUN=0: the flag is what it ADDS when you did not ask to build. Defaulting the empty
# case to dry-run instead makes `make package DRY_RUN=0` print the preview and build
# nothing, and the stale artifact from a previous run then sails through `verify`.
case "${1:-}" in
    --dry-run) MODE="dry-run" ;;
    --dev)     MODE="dev" ;;
    *)         MODE="release" ;;
esac

VERSION="$(read_version)"

if [[ "$MODE" == "dry-run" ]]; then
    printf 'package (dry-run) — %s\n\n' "$PRODUCT_LABEL"
    printf '  version    %s\n' "$VERSION"
    [[ -n "${PRE_PACKAGE:-}" ]] && printf '  first      %s\n' "$PRE_PACKAGE"
    for i in "${!APP_PATHS[@]}"; do
        printf '  app        %-40s -> %s  (warning <= %s)\n' "${APP_PATHS[$i]}/" \
               "$(artifact_path "${APP_NAMES[$i]}" "$VERSION")" "${APP_BUDGETS[$i]}"
    done
    printf '  gate       slim validate + splunk-appinspect --mode precert\n'
    printf '  image      %s\n\n' "$APPINSPECT_IMAGE"
    printf 'Build the release artifacts: make package DRY_RUN=0\n'
    printf 'Build them to try locally:   make package DEV=1\n'
    exit 0
fi

command -v docker >/dev/null 2>&1 || {
    echo "Error: docker is not available, and the toolchain (slim + appinspect) lives in" >&2
    echo "       $APPINSPECT_IMAGE." >&2
    exit 1
}

# Refused BEFORE anything runs: PRE_PACKAGE may write into the tree, and a generator that
# ran on a dirty tree has already produced output no commit describes.
if [[ "$MODE" == "release" && -n "$(git status --porcelain)" ]]; then
    echo "Error: the working tree has uncommitted changes." >&2
    echo "       The artifacts have to correspond to a commit; commit or stash first," >&2
    echo "       or build dev ones with: make package DEV=1" >&2
    exit 1
fi

run_pre_package
require_app_dirs
mkdir -p dist

# --- dev build ------------------------------------------------------------------
#
# Packaged from a COPY, never from the tree: the dev version has to end up inside
# app.conf or Splunk installs it under the release version and the two become
# indistinguishable in the app list — which is the whole point of the suffix. Writing it
# into the real manifest and restoring afterwards would leave the repo corrupted the first
# time the script dies between the two steps.
if [[ "$MODE" == "dev" ]]; then
    DEV_VERSION="${VERSION}-dev.$(date +%y%m%d%H%M)"
    BUILD="dist/.dev-build"
    rm -rf "$BUILD"; mkdir -p "$BUILD"
    for i in "${!APP_PATHS[@]}"; do
        name="${APP_NAMES[$i]}"
        cp -r "${APP_PATHS[$i]}" "$BUILD/$name"
        ( MANIFEST="$PROJECT_ROOT/$BUILD/$name/default/app.conf"; write_version "$DEV_VERSION" )
        echo "==> Packaging $name $DEV_VERSION from a copy (the tree is untouched)"
        # slim validate but no AppInspect: a dev build is not going to be published, and
        # the gate is the slowest part of the loop this mode exists to shorten.
        docker run --rm --user root -v "$PROJECT_ROOT":/w -w /w "$APPINSPECT_IMAGE" bash -ec "
            slim package $BUILD/$name >/dev/null
            slim validate $BUILD/$name
        "
        mv -f "${name}-${DEV_VERSION}.tar.gz" "dist/"
    done
    rm -rf "$BUILD"

    echo
    for name in "${APP_NAMES[@]}"; do echo "Dev artifact: dist/${name}-${DEV_VERSION}.tar.gz"; done
    echo "  NOT gated by AppInspect, and not release artifacts — install them and try them."
    exit 0
fi

# --- release artifacts ----------------------------------------------------------
failed=0
for i in "${!APP_PATHS[@]}"; do
    path="${APP_PATHS[$i]}" name="${APP_NAMES[$i]}" budget="${APP_BUDGETS[$i]}"
    TARBALL="${name}-${VERSION}.tar.gz"
    REPORT="$(appinspect_file "$name")"
    # slim writes an app.manifest into the app directory. Removed afterwards only if it
    # was not there before: in a UCC build ucc-gen puts one there on purpose.
    had_manifest=0; [[ -f "$path/app.manifest" ]] && had_manifest=1

    echo "==> $name: packaging and validating in $APPINSPECT_IMAGE"
    # --user root: the image runs as a non-root user and the bind mount belongs to the host.
    docker run --rm --user root -v "$PROJECT_ROOT":/w -w /w "$APPINSPECT_IMAGE" bash -ec "
        slim package $path >/dev/null
        echo '--- slim validate ---'
        slim validate $path
    "
    (( had_manifest )) || rm -f "$path/app.manifest"
    # slim names the tarball after the version INSIDE the app. Not finding it under this
    # version means the app does not carry it: for a generated one, PRE_PACKAGE (or
    # POST_BUMP) did not re-derive it — the drift a shared version exists to prevent.
    if [[ ! -f "$TARBALL" ]]; then
        echo "Error: slim did not produce $TARBALL. $path/default/app.conf does not carry" >&2
        echo "       $VERSION; if it is generated, PRE_PACKAGE did not re-derive the version." >&2
        ls "${name}"-*.tar.gz 2>/dev/null | sed 's/^/       produced instead: /' >&2
        rm -f "${name}"-*.tar.gz
        exit 1
    fi
    echo '--- appinspect ---'
    docker run --rm --user root -v "$PROJECT_ROOT":/w -w /w "$APPINSPECT_IMAGE" \
        splunk-appinspect inspect "$TARBALL" --output-file "/w/$REPORT" --mode precert >/dev/null
    mv -f "$TARBALL" "$(artifact_path "$name" "$VERSION")"

    read -r ERRORS FAILURES WARNINGS <<<"$(jq -r '.summary | "\(.error) \(.failure) \(.warning)"' "$REPORT")"
    SUMMARY="$(jq -c '.summary' "$REPORT")"
    if (( ERRORS > 0 || FAILURES > 0 || WARNINGS > budget )); then
        echo "    Gate FAILED: $SUMMARY  (budget: error=0 failure=0 warning<=$budget)" >&2
        failed=1
    else
        echo "    Gate OK: $SUMMARY"
    fi
done

echo
if (( failed )); then
    echo "At least one artifact failed its gate; do not promote." >&2
    exit 1
fi
for name in "${APP_NAMES[@]}"; do echo "Artifact: $(artifact_path "$name" "$VERSION")"; done
echo
echo "Next: make verify, then make promote-main and make release."
