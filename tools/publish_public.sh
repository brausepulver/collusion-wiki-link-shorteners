#!/usr/bin/env bash
# Rebuild the public branch: export the filtered tree (tools/public_export.py), commit it as ONE root commit on
# branch `public` (no history), and print the push command. Never pushes by itself.
#   tools/publish_public.sh [branch]      (default branch: public)
set -euo pipefail
cd "$(dirname "$0")/.."
BR=${1:-public}
CUTOFF=${CUTOFF:-2026-08-31}
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
python3 tools/public_export.py "$TMP/tree" --cutoff "$CUTOFF" | tail -40
export GIT_INDEX_FILE="$TMP/index"
git --work-tree="$TMP/tree" add -A
TREE=$(git write-tree)
MSG="Collusion-wiki link-shortener investigation: public data release ($(date -u +%Y-%m-%d))

Single-commit public snapshot built by tools/public_export.py from the working tree.
Held back: data after $CUTOFF, non-agent creator IPs (residential /16 only), links not made by the agents, root working notes."
COMMIT=$(printf '%s\n' "$MSG" | git commit-tree "$TREE")
git update-ref "refs/heads/$BR" "$COMMIT"
unset GIT_INDEX_FILE
echo
echo "branch $BR -> $(git rev-parse --short "$COMMIT")  ($(git ls-tree -r --name-only "$COMMIT" | wc -l) files)"
echo "to publish (replaces the remote history):  git push --force origin $BR:main"
