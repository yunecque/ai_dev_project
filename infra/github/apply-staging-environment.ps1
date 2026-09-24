<#
.SYNOPSIS
  Create/update the `staging` environment used by the independent deploy-verify gate.

.DESCRIPTION
  Requires the GitHub CLI (`gh`) authenticated against the target repository.
  Idempotent: overwrites the environment configuration with the values below.
  Solo-mode policy (ADR-0013): no required reviewers; the gate is enforced by the
  independent signature/SBOM/provenance checks and the fail-closed pre-deployment policy.

.EXAMPLE
  ./apply-staging-environment.ps1 -Repo yunecque/ai_dev_project
#>
param(
  [Parameter(Mandatory = $true)][string]$Repo,
  [string]$Environment = "staging"
)

$ErrorActionPreference = "Stop"

$payload = @{
  wait_timer                = 0
  deployment_branch_policy  = @{
    protected_branches     = $true
    custom_branch_policies = $false
  }
} | ConvertTo-Json -Depth 6

Write-Host "Applying environment '$Environment' to $Repo ..."
$payload | gh api -X PUT "repos/$Repo/environments/$Environment" --input - | Out-Null
Write-Host "Done. Verify in Settings -> Environments -> $Environment."
