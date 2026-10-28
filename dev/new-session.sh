#!/usr/bin/env bash
# Make a git worktree for a parallel Claude Code session (docs/SESSIONS.md).
#
#   dev/new-session.sh <name>
#
# Creates ../cqa-<name> (next to the main folder) on a new branch session/<name> from main's
# HEAD, copies .env into it if there is one (it stays uncommitted: .gitignore covers it), and
# adds docs/handoff/<name>.md from the template if it is missing. It checks everything before it
# changes anything, and refuses if the branch or the folder already exists, so running it again
# changes nothing. dev/new-session.ps1 does the same from PowerShell.

set -euo pipefail

fail() {
    echo "error: $*" >&2
    exit 1
}

if [ "$#" -ne 1 ]; then
    echo "usage: dev/new-session.sh <name>   (lowercase letters, digits and hyphens)" >&2
    exit 2
fi
name=$1
if ! [[ $name =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    fail "'$name' is not a valid session name: use lowercase letters, digits and hyphens"
fi

common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) \
    || fail "run this inside the cosmic-quiz-agent repo"
# The main folder, even when this runs from another worktree.
primary=$(dirname "$common")
target="$(dirname "$primary")/cqa-$name"
branch="session/$name"
handoff="docs/handoff/$name.md"
template="docs/handoff/TEMPLATE.md"

git -C "$primary" rev-parse --verify --quiet main >/dev/null || fail "there is no main branch"
if git -C "$primary" show-ref --verify --quiet "refs/heads/$branch"; then
    fail "branch $branch already exists; its worktree, if any, is listed by 'git worktree list'"
fi
if [ -e "$target" ]; then
    fail "$target already exists; nothing was changed"
fi
if ! git -C "$primary" cat-file -e "main:$template" 2>/dev/null; then
    fail "main has no $template; commit the parallel-session files first"
fi

base=$(git -C "$primary" rev-parse --short main)
git -C "$primary" worktree add -b "$branch" "$target" main
echo "Made $target on $branch from main at $base."

if [ -f "$primary/.env" ]; then
    git -C "$target" check-ignore -q .env || fail ".env is not ignored in $target; not copying it"
    cp "$primary/.env" "$target/.env"
    echo "Copied .env (ignored by git; never commit it)."
else
    echo "No .env in $primary; copy one in before running anything that needs secrets."
fi

if [ -e "$target/$handoff" ]; then
    echo "$handoff already exists; left as it is."
else
    sed "s/<session>/$name/g" "$target/$template" >"$target/$handoff"
    echo "Made $handoff from the template (uncommitted; commit it on $branch)."
fi

cat <<EOF

Next steps:
  1. Open the folder in VS Code:
       code "$target"
  2. Set it up once (a worktree has no .venv or node_modules of its own):
       python -m venv .venv
       source .venv/Scripts/activate
       pip install -r requirements-dev.txt
       pnpm install
  3. Add a row for "$name" to docs/SESSIONS.md, "Active sessions", or let Claude do it.
  4. Give Claude this first message:

Read CLAUDE.md, docs/SESSIONS.md and docs/handoff/$name.md, then docs/DESIGN.md and docs/PLAN.md. You are the "$name" session, in the worktree $target on branch $branch. Claim or update your row in docs/SESSIONS.md, follow "Parallel sessions" in CLAUDE.md, and edit only the files your session owns. Tell me your plan before changing code.
EOF
