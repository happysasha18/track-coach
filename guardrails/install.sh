#!/usr/bin/env bash
# Install the track-coach git hooks. Safe to re-run — overwrites with the current guardrails/ copies.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
cp "$REPO_ROOT/guardrails/pre-push" "$REPO_ROOT/.git/hooks/pre-push"
chmod +x "$REPO_ROOT/.git/hooks/pre-push"
echo "installed: .git/hooks/pre-push"
