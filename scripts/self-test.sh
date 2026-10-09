#!/usr/bin/env bash
# kudaw-delivery: v1.10.0
# Level 2 of the contract's validation: do the deterministic targets do what they say?
#
# Usage:
#   scripts/self-test.sh
#
# Level 1 (contract-check) asserts that `make bump` exists. This asserts that it writes
# the version it claims and leaves the tree exactly as it found it. Read-only except for
# one bump that is undone and verified byte-for-byte. The preconditions of release and
# promote are proven in a throwaway sandbox under $TMPDIR, never on this repo.
#
# It refuses to run on a dirty manifest: it cannot promise to restore what it did not
# write.

set -euo pipefail

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"

# In a monorepo any package proves the round trip, so pick the first instead of making
# the caller choose. Re-sourced with PKG exported, so the version.sh calls below see it.
if [[ -z "$MANIFEST_REL" && -n "${PACKAGES:-}" ]]; then
    PKG="$(awk 'NF {print $1; exit}' <<< "$PACKAGES")"
    export PKG
    NEEDS_MANIFEST=1
    # shellcheck source=/dev/null
    source "$(dirname "${BASH_SOURCE[0]}")/_config.sh"
    echo "Monorepo: testing the round trip on '$PKG' (PKG= to pick another)."
fi
cd "$PROJECT_ROOT"

pass=0; fail=0
ok()   { printf '  ✓ %s\n' "$1"; pass=$((pass + 1)); }
bad()  { printf '  ✗ %s\n' "$1"; fail=$((fail + 1)); }

echo "Self-test — $PRODUCT_LABEL ($MANIFEST_FLAVOUR)"
echo

if [[ -n "$(git status --porcelain "$MANIFEST_REL")" ]]; then
    echo "Error: $MANIFEST_REL has uncommitted changes; refusing to touch it." >&2
    exit 2
fi

# With POST_BUMP the round trip also writes the files derived from the manifest, so the
# promise widens from "the manifest is back" to "the tree is back". Snapshotted up front:
# a tree that was dirty before is compared to itself, not to clean.
tree_before="$(git status --porcelain)"

echo "Version:"
before="$(bash scripts/version.sh get)"
if [[ "$before" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    ok "get -> $before (MAJOR.MINOR.PATCH)"
else
    bad "get -> '$before' is not a SemVer triple"
fi

# The round trip: bump, confirm the write landed, put it back, confirm byte equality.
expected="$(awk -F. '{printf "%d.%d.%d", $1, $2, $3 + 1}' <<< "$before")"
bash scripts/version.sh bump patch >/dev/null
after="$(bash scripts/version.sh get)"
[[ "$after" == "$expected" ]] && ok "bump patch -> $expected" \
                              || bad "bump patch -> '$after', expected '$expected'"
bash scripts/version.sh set "$before" >/dev/null
[[ "$(bash scripts/version.sh get)" == "$before" ]] && ok "set restores $before" \
                                                    || bad "set did not restore $before"
if [[ -z "$(git status --porcelain "$MANIFEST_REL")" ]]; then
    ok "the manifest is byte-identical to where it started"
else
    bad "the round trip left $MANIFEST_REL modified — the writer is not reversible"
    git --no-pager diff -- "$MANIFEST_REL" >&2
fi

if [[ -n "${POST_BUMP:-}" ]]; then
    # The round trip recorded what POST_BUMP touched, for a `changelog` that is not coming.
    rm -f "$(post_bump_record)"
    if [[ "$(git status --porcelain)" == "$tree_before" ]]; then
        ok "POST_BUMP ran both ways and left the tree as it found it"
    else
        bad "POST_BUMP did not restore what it derives — the round trip left changes:"
        diff <(echo "$tree_before") <(git status --porcelain) >&2 || true
    fi
fi

[[ "$(bash scripts/version.sh manifest)" == "$MANIFEST_REL" ]] \
    && ok "manifest -> $MANIFEST_REL" || bad "manifest does not report $MANIFEST_REL"

echo
echo "Baseline and classification:"
baseline="$(bash scripts/version.sh baseline 2>/dev/null || true)"
if [[ -n "$baseline" ]]; then
    ok "baseline -> $baseline"
else
    ok "baseline -> none (no release yet; valid for a repo that has not shipped)"
fi
level="$(bash scripts/version.sh suggest --level-only)"
case "$level" in
    none|patch|minor|major) ok "suggest --level-only -> $level" ;;
    *) bad "suggest --level-only -> '$level', not one of none/patch/minor/major" ;;
esac

echo
echo "Release notes:"
if bash scripts/release-notes.sh "$before" >/dev/null 2>&1; then
    ok "release-notes runs for $before"
else
    bad "release-notes failed for $before"
fi
if bash scripts/changelog.sh has "$before"; then
    ok "the CHANGELOG has an entry for $before"
else
    ok "no CHANGELOG entry for $before yet (expected before its \`changelog\` runs)"
fi

# --- release and promote, in a sandbox ------------------------------------------
#
# release and promote are the irreversible targets, so the repo itself is never where they
# are proven. Their PRECONDITIONS are what keeps them safe, and those are testable: a
# throwaway clone with its own --bare origin, this repo's scripts copied in, a `gh` stub on
# the PATH so nothing reaches GitHub. What each case asserts is the remote's state after —
# a precondition that fails after the push is not a precondition.
#
# Every flavour is exercised, not just this repo's: a check that only works for the
# flavour it was written against passes here and breaks the next repo that adopts it.

echo
echo "Release and promote (sandbox, nothing leaves this machine):"

SANDBOX="$(mktemp -d -t kudaw-self-test-XXXXXX)"
trap 'rm -rf "$SANDBOX"' EXIT
mkdir -p "$SANDBOX/bin"
cat > "$SANDBOX/bin/gh" <<'STUB'
#!/usr/bin/env bash
# gh stub: `release view` answers with a URL, everything else succeeds silently.
[[ "${1:-} ${2:-}" == "release view" ]] && echo "https://example.invalid/release"
exit 0
STUB
chmod +x "$SANDBOX/bin/gh"

# The sandbox must not inherit this machine's git config (signing, hooks, a default
# branch) nor this repo's delivery variables. A subshell with exports and not `env`: `env`
# is resolved through the PATH, and a tool that drops its own `env` in ~/.local/bin (uv
# does) turns every sandbox call into a silent no-op.
sx() (
    unset PKG RELEASE_ASSETS TAG_PREFIX
    export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
    export GIT_AUTHOR_NAME=self-test GIT_AUTHOR_EMAIL=self-test@invalid
    export GIT_COMMITTER_NAME=self-test GIT_COMMITTER_EMAIL=self-test@invalid
    export PATH="$SANDBOX/bin:$PATH"
    "$@"
)

# A manifest carrying 1.0.0 in each flavour's own syntax.
fixture_manifest() {
    case "$1" in
        app-conf)       echo "myapp/default/app.conf"
                        printf '[id]\nname = myapp\nversion = 1.0.0\n\n[launcher]\nversion = 1.0.0\n' ;;
        package-json)   echo "package.json"
                        printf '{\n  "name": "myapp",\n  "version": "1.0.0"\n}\n' ;;
        pyproject-toml) echo "pyproject.toml"
                        printf '[project]\nname = "myapp"\nversion = "1.0.0"\n' ;;
        *)              return 1 ;;
    esac
}

# new_sandbox <name> <flavour> [extra delivery.conf lines] -> prints the clone's path.
new_sandbox() {
    local name="$1" flavour="$2" extra="${3:-}" dir="$SANDBOX/$1" content rel
    content="$(fixture_manifest "$flavour")" || return 1
    rel="$(head -1 <<< "$content")"
    sx git init -q --bare "$dir.git" && sx git clone -q "$dir.git" "$dir" 2>/dev/null \
        || { echo "Error: could not create the sandbox '$name'." >&2; return 1; }
    # `cd || exit` in every subshell that enters a sandbox, and not `set -e`: bash ignores
    # -e inside a subshell whose status is tested, and a failed cd there would write the
    # fixtures and commits into THIS repo instead.
    (
        cd "$dir" || exit 1
        sx git checkout -q -b main
        mkdir -p scripts "$(dirname "$rel")"
        cp -r "$PROJECT_ROOT/scripts/." scripts/
        tail -n +2 <<< "$content" > "$rel"
        printf 'PRODUCT_LABEL="Self-test"\nPROFILE="app-splunk"\nMANIFEST="%s"\nMANIFEST_FLAVOUR="%s"\n%s\n' \
            "$rel" "$flavour" "$extra" > delivery.conf
        sx git add -A && sx git commit -qm "feat: initial"
        sx git push -q origin main 2>/dev/null
    ) || { echo "Error: could not build the sandbox '$name'." >&2; return 1; }
    printf '%s\n' "$dir"
}

remote_has_tag() { sx git --git-dir="$1.git" rev-parse -q --verify "refs/tags/$2" >/dev/null; }

log="$SANDBOX/last.log"
for flavour_file in "$PROJECT_ROOT"/scripts/manifest/*.sh; do
    flavour="$(basename "$flavour_file" .sh)"
    if ! fixture_manifest "$flavour" >/dev/null; then
        ok "release precondition: no fixture for flavour '$flavour' (add one to self-test)"
        continue
    fi
    dir="$(new_sandbox "rel-$flavour" "$flavour")"
    if (cd "$dir" && sx bash scripts/release.sh 1.0.0) >"$log" 2>&1 && remote_has_tag "$dir" v1.0.0; then
        ok "release finds 1.0.0 on origin/main ($flavour)"
    else
        bad "release does not find 1.0.0 on origin/main ($flavour):"
        sed 's/^/      /' "$log" >&2
    fi
    if ! (cd "$dir" && sx bash scripts/release.sh 9.9.9) >"$log" 2>&1 && ! remote_has_tag "$dir" v9.9.9; then
        ok "release refuses 9.9.9, which origin/main does not carry ($flavour)"
    else
        bad "release accepted 9.9.9, which origin/main does not carry ($flavour)"
    fi
done

# A declared artifact that is not built: refused before anything is created remotely. On
# package-json, whose version check held even before app-conf's did, so this case never
# rides on an earlier precondition failing first.
dir="$(new_sandbox rel-assets package-json "RELEASE_ASSETS='dist/myapp-\${VERSION}.tar.gz'")"
if ! (cd "$dir" && sx bash scripts/release.sh 1.0.0) >"$log" 2>&1 && ! remote_has_tag "$dir" v1.0.0; then
    ok "release with a missing RELEASE_ASSETS fails without pushing the tag"
else
    bad "release with a missing RELEASE_ASSETS pushed v1.0.0 anyway (or did not fail)"
fi

# TAG_PREFIX="" — bare SemVer tags. The tag release creates, the one release-notes looks
# for and the one the CHANGELOG dates itself from all have to be the same name: before the
# prefix was configurable each of them hardcoded `v` on its own.
dir="$(new_sandbox rel-bare pyproject-toml 'TAG_PREFIX=""')"
if (cd "$dir" && sx bash scripts/release.sh 1.0.0) >"$log" 2>&1 \
   && remote_has_tag "$dir" 1.0.0 && ! remote_has_tag "$dir" v1.0.0; then
    ok "release with TAG_PREFIX=\"\" tags 1.0.0, not v1.0.0"
else
    bad "release with TAG_PREFIX=\"\" did not tag a bare 1.0.0:"
    sed 's/^/      /' "$log" >&2
fi
# With only the bare tag in place, release-notes has to range up to it — not fall back to
# HEAD for want of a v1.0.0, which would pull in the commit made after the release. The
# released commit has to be IN the notes too: an empty range also leaves that one out. Its own
# sandbox, so no v1.0.0 left behind by a release above can answer in its place.
dir="$(new_sandbox notes-bare pyproject-toml 'TAG_PREFIX=""')"
if (cd "$dir" && sx git tag -a 1.0.0 -m "Release 1.0.0" && echo x > x.txt && sx git add -A \
        && sx git commit -qm "feat: after the release" \
        && sx bash scripts/release-notes.sh 1.0.0) >"$log" 2>&1 \
   && grep -q "initial" "$log" && ! grep -q "after the release" "$log"; then
    ok "release-notes with TAG_PREFIX=\"\" ranges up to tag 1.0.0, not HEAD"
else
    bad "release-notes with TAG_PREFIX=\"\" did not stop at tag 1.0.0:"
    sed 's/^/      /' "$log" >&2
fi
# An inherited TAG_PREFIX is ignored: only delivery.conf names the tag. A guard, not a
# fix — v1.9.0 held it by never reading the variable at all.
dir="$(new_sandbox rel-env-prefix pyproject-toml)"
if (cd "$dir" && sx bash -c 'export TAG_PREFIX=x; bash scripts/release.sh 1.0.0') >"$log" 2>&1 \
   && remote_has_tag "$dir" v1.0.0 && ! remote_has_tag "$dir" x1.0.0; then
    ok "a TAG_PREFIX from the environment does not rename the tag"
else
    bad "a TAG_PREFIX from the environment renamed the tag:"
    sed 's/^/      /' "$log" >&2
fi

# promote from develop with a commit that only exists locally: refused, remote untouched.
# Both shapes — with and without something already pushed — since the second one used to
# answer "Nothing to promote" and drop the local commit without a word.
for shape in with-pushed only-local; do
    dir="$(new_sandbox "promote-$shape" app-conf)"
    (
        cd "$dir" || exit 1
        sx git checkout -q -b develop && sx git push -q origin develop 2>/dev/null
        if [[ "$shape" == with-pushed ]]; then
            echo pushed > pushed.txt && sx git add -A && sx git commit -qm "feat: pushed"
            sx git push -q origin develop 2>/dev/null
        fi
        echo local > local.txt && sx git add -A && sx git commit -qm "feat: local only"
    )
    main_before="$(sx git --git-dir="$dir.git" rev-parse main)"
    if ! (cd "$dir" && sx bash scripts/promote.sh main) >"$log" 2>&1 \
       && [[ "$(sx git --git-dir="$dir.git" rev-parse main)" == "$main_before" ]]; then
        ok "promote main refuses a develop with unpushed commits ($shape)"
    else
        bad "promote main did not refuse a develop with unpushed commits ($shape):"
        sed 's/^/      /' "$log" >&2
    fi
done

echo
echo "$pass passed, $fail failed."
(( fail == 0 ))
