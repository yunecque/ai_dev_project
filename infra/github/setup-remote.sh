#!/usr/bin/env bash
# One-command GitHub control-plane setup for the Secure Agentic SDLC repository.
#
# Prerequisite: `gh auth login` has been completed (device flow is interactive).
#
# What it does:
#   1. verifies gh authentication and that the working tree has commits;
#   2. creates the remote repository (if missing) and pushes `main`;
#   3. applies branch protection with the ordered required checks (constitution section 9).
#
# Usage:
#   bash infra/github/setup-remote.sh [repo-name] [public|private]
#
# Note: keyless Cosign signing / artifact attestations work best on a public repo
#       (or a private repo with GitHub OIDC). Solo-mode staging uses environment approvals.

set -euo pipefail

REPO_NAME="${1:-ai_dev_project}"
VISIBILITY="${2:-public}"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

command -v gh >/dev/null 2>&1 || die "gh not found in PATH (run infra/wsl/bootstrap-toolchain.sh)"

gh auth status >/dev/null 2>&1 || die "not logged in. Run: gh auth login"

git rev-parse --verify HEAD >/dev/null 2>&1 || die "no commits yet. Commit the M0 baseline first."

OWNER="$(gh api user --jq .login)"
log "owner=${OWNER} repo=${REPO_NAME} visibility=${VISIBILITY}"

if gh repo view "${OWNER}/${REPO_NAME}" >/dev/null 2>&1; then
  log "repository ${OWNER}/${REPO_NAME} already exists"
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "https://github.com/${OWNER}/${REPO_NAME}.git"
else
  log "creating repository"
  gh repo create "${OWNER}/${REPO_NAME}" "--${VISIBILITY}" --source=. --remote=origin --push
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
log "pushing ${BRANCH}"
git push -u origin "${BRANCH}"

REQUIRED_CHECKS='["schema-validate","lint","typecheck","secret-scan","unit-tests","contract-tests","sast","dependency-scan","integration-tests","security-tests","policy-check","build-image","container-scan","sbom-generate","sign-and-attest"]'

log "applying branch protection to ${BRANCH}"
gh api -X PUT "repos/${OWNER}/${REPO_NAME}/branches/${BRANCH}/protection" \
  --input - <<JSON
{
  "required_status_checks": { "strict": true, "contexts": ${REQUIRED_CHECKS} },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1
  },
  "required_conversation_resolution": true,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

log "done: https://github.com/${OWNER}/${REPO_NAME}"
log "next: create the 'staging' environment with a required reviewer (release-approver)."
