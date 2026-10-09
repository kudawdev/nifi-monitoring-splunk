# kudaw-delivery: v1.8.0
# Shared bits of the app-splunk artifact scripts: which apps the repo ships, what each one
# builds into, and the gate each has to pass.
#
# ONE APP is the common case and needs no configuration: a Splunk app's manifest is always
# <app>/default/app.conf, so the app directory is the manifest's grandparent. Asking for a
# value the layout already answers is how delivery.conf grows into a second manifest.
#
# SEVERAL APPS — an app plus its add-on, say — are declared in APP_DIRS, one entry per
# shipped package, each optionally carrying its own AppInspect warning budget:
#
#     APP_DIRS="nifi_monitoring:5 output/nifi_TA_monitoring:12"
#
# An entry is a PATH, not a name, because an add-on built with UCC is packaged from what
# ucc-gen generates (output/<ta>), not from its source. The artifact is named by the last
# component, which is what slim names it. They share the one version the manifest holds:
# a release is a set of packages that ship together, and `verify` checks every one of them
# carries it. What keeps a generated one in step is POST_BUMP; what generates it before
# packaging is PRE_PACKAGE.

APPINSPECT_IMAGE="${APPINSPECT_IMAGE:-kudaw/appinspect:4.2.1}"
APPINSPECT_MAX_WARNING="${APPINSPECT_MAX_WARNING:-8}"

# APP_DIR is the one-app override, kept so a conf written before APP_DIRS still works.
if [[ -z "${APP_DIRS:-}" ]]; then
    APP_DIRS="${APP_DIR:-$(basename "$(dirname "$(dirname "$MANIFEST")")")}"
fi

APP_PATHS=() APP_NAMES=() APP_BUDGETS=()
for entry in $APP_DIRS; do
    path="${entry%%:*}"
    budget="$APPINSPECT_MAX_WARNING"
    [[ "$entry" == *:* ]] && budget="${entry##*:}"
    if [[ ! "$budget" =~ ^[0-9]+$ ]]; then
        echo "Error: APP_DIRS entry '$entry' has a budget that is not a number." >&2
        exit 2
    fi
    APP_PATHS+=("${path%/}"); APP_NAMES+=("$(basename "$path")"); APP_BUDGETS+=("$budget")
done
unset entry path budget
if (( ${#APP_PATHS[@]} == 0 )); then
    echo "Error: APP_DIRS is set but lists no app." >&2
    exit 2
fi

artifact_path()   { printf 'dist/%s-%s.tar.gz\n' "$1" "$2"; }   # <name> <version>
appinspect_file() { printf 'dist/appinspect-%s.json\n' "$1"; }  # <name>

# A generated app does not exist until PRE_PACKAGE ran, so this is asked when it matters —
# before packaging — and not on load, where it would fail every `make status`.
require_app_dirs() {
    local i missing=0
    for i in "${!APP_PATHS[@]}"; do
        if [[ ! -d "$PROJECT_ROOT/${APP_PATHS[$i]}" ]]; then
            echo "Error: the app directory '${APP_PATHS[$i]}' does not exist." >&2
            missing=1
        fi
    done
    if (( missing )); then
        echo "       One app is derived from MANIFEST ($MANIFEST); several are declared in" >&2
        echo "       APP_DIRS. A generated one needs PRE_PACKAGE to build it first." >&2
        exit 2
    fi
}

run_pre_package() {
    [[ -z "${PRE_PACKAGE:-}" ]] && return 0
    echo "==> PRE_PACKAGE: $PRE_PACKAGE"
    if ! (cd "$PROJECT_ROOT" && bash -c "$PRE_PACKAGE"); then
        echo "Error: PRE_PACKAGE failed; nothing was packaged." >&2
        exit 1
    fi
}
