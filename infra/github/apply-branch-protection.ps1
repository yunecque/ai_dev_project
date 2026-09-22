<#
.SYNOPSIS
  Apply branch protection for `main` and staging environment required checks.

.DESCRIPTION
  Requires the GitHub CLI (`gh`) authenticated against the target repository.
  Idempotent: overwrites the existing protection with the values below.

.EXAMPLE
  ./apply-branch-protection.ps1 -Repo zarl3/ai_dev_project
#>
param(
  [Parameter(Mandatory = $true)][string]$Repo,
  [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"

$requiredChecks = @(
  "schema-validate", "lint", "typecheck", "secret-scan", "unit-tests",
  "contract-tests", "sast", "dependency-scan", "integration-tests",
  "security-tests", "policy-check", "build-image", "container-scan",
  "sbom-generate", "sign-and-attest"
)

$contexts = $requiredChecks | ForEach-Object { @{ context = $_ } }

$payload = @{
  required_status_checks = @{
    strict   = $true
    contexts = $requiredChecks
  }
  enforce_admins            = $true
  required_pull_request_reviews = @{
    dismiss_stale_reviews           = $true
    require_code_owner_reviews      = $true
    required_approving_review_count = 1
  }
  required_conversation_resolution = $true
  restrictions              = $null
  allow_force_pushes        = $false
  allow_deletions           = $false
} | ConvertTo-Json -Depth 6

Write-Host "Applying branch protection to $Repo@$Branch ..."
$payload | gh api -X PUT "repos/$Repo/branches/$Branch/protection" --input - | Out-Null
Write-Host "Done. Verify in Settings -> Branches."
