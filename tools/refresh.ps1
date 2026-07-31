<#
    refresh.ps1

    Rebuilds the profile cards and pushes them if anything changed.

    Runs from the Windows scheduled task "profile-cards-refresh". It authenticates
    through the GitHub CLI credential helper, which reads the token from the user's
    credential store - no browser session is involved and no token is stored in this
    repository. That is why this runs locally instead of in GitHub Actions: counting
    private contributions needs a token with repository access, and putting one in
    the secrets of a public repository is more privilege than the job deserves.

    The build script refuses to write when the totals collapse, so a broken
    credential leaves the last good cards in place instead of overwriting them.
#>
[CmdletBinding()]
param(
    [string]$RepoPath = "Z:\MyLittleSpace\github\classified-mick",
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"
Set-Location $RepoPath

function Invoke-Git {
    param([string[]]$GitArgs)
    $out = & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') failed (exit $LASTEXITCODE): $out" }
    return $out
}

Invoke-Git @('fetch', '--quiet', 'origin')
Invoke-Git @('pull',  '--quiet', '--rebase', 'origin', 'main')

python "$RepoPath\tools\build_profile.py"
if ($LASTEXITCODE -ne 0) {
    throw "build_profile.py exited $LASTEXITCODE - cards left untouched"
}

if (& git status --porcelain -- assets) {
    Invoke-Git @('config', 'user.name',  'Mykhailo Kholiev')
    Invoke-Git @('config', 'user.email', 'classifiedprofi@gmail.com')
    Invoke-Git @('add', '--', 'assets')
    Invoke-Git @('commit', '-q', '-m', 'Refresh profile cards')
    Write-Output "cards changed, committed"
} else {
    Write-Output "cards unchanged"
}

# Push on "the branch is ahead", not on "I just committed". A previous run that
# was told not to push, or that died after committing, would otherwise leave the
# commit stranded here forever while every later run reported success.
$ahead = (& git rev-list --count 'origin/main..HEAD').Trim()
if ($ahead -eq '0') {
    Write-Output "nothing to push"
    exit 0
}

if ($NoPush) {
    Write-Output "$ahead commit(s) ready, push skipped"
} else {
    Invoke-Git @('push', '--quiet', 'origin', 'main')
    Write-Output "pushed $ahead commit(s)"
}
