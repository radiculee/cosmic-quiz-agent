# Make a git worktree for a parallel Claude Code session (docs/SESSIONS.md).
#
#   powershell -ExecutionPolicy Bypass -File dev\new-session.ps1 <name>
#
# Creates ..\cqa-<name> (next to the main folder) on a new branch session/<name> from main's
# HEAD, copies .env into it if there is one (it stays uncommitted: .gitignore covers it), and
# adds docs\handoff\<name>.md from the template if it is missing. It checks everything before it
# changes anything, and refuses if the branch or the folder already exists, so running it again
# changes nothing. dev/new-session.sh does the same from Git Bash. Written for Windows
# PowerShell 5.1.

param([string]$Name)

# Not 'Stop': in PowerShell 5.1 that turns git's progress lines on stderr into errors. Every git
# call checks $LASTEXITCODE instead, and each cmdlet that matters passes -ErrorAction Stop.

function Fail([string]$Message) {
    [Console]::Error.WriteLine("error: $Message")
    exit 1
}

if (-not $Name) {
    [Console]::Error.WriteLine('usage: dev\new-session.ps1 <name>   (lowercase letters, digits and hyphens)')
    exit 2
}
if ($Name -cnotmatch '^[a-z0-9][a-z0-9-]*$') {
    Fail "'$Name' is not a valid session name: use lowercase letters, digits and hyphens"
}

$common = git rev-parse --path-format=absolute --git-common-dir 2>$null
if ($LASTEXITCODE -ne 0 -or -not $common) { Fail 'run this inside the cosmic-quiz-agent repo' }
# The main folder, even when this runs from another worktree.
$primary = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($common))
$target = Join-Path ([System.IO.Path]::GetDirectoryName($primary)) "cqa-$Name"
$branch = "session/$Name"
$handoff = "docs/handoff/$Name.md"
$template = 'docs/handoff/TEMPLATE.md'

git -C $primary rev-parse --verify --quiet main | Out-Null
if ($LASTEXITCODE -ne 0) { Fail 'there is no main branch' }
git -C $primary show-ref --verify --quiet "refs/heads/$branch"
if ($LASTEXITCODE -eq 0) {
    Fail "branch $branch already exists; its worktree, if any, is listed by 'git worktree list'"
}
if (Test-Path -LiteralPath $target) { Fail "$target already exists; nothing was changed" }
git -C $primary cat-file -e "main:$template" 2>$null
if ($LASTEXITCODE -ne 0) { Fail "main has no $template; commit the parallel-session files first" }

$base = git -C $primary rev-parse --short main
git -C $primary worktree add -b $branch $target main
if ($LASTEXITCODE -ne 0) { Fail "git worktree add failed" }
Write-Output "Made $target on $branch from main at $base."

$envFile = Join-Path $primary '.env'
if (Test-Path -LiteralPath $envFile) {
    git -C $target check-ignore -q .env
    if ($LASTEXITCODE -ne 0) { Fail ".env is not ignored in $target; not copying it" }
    Copy-Item -LiteralPath $envFile -Destination (Join-Path $target '.env') -ErrorAction Stop
    Write-Output 'Copied .env (ignored by git; never commit it).'
} else {
    Write-Output "No .env in $primary; copy one in before running anything that needs secrets."
}

$handoffPath = Join-Path $target $handoff
if (Test-Path -LiteralPath $handoffPath) {
    Write-Output "$handoff already exists; left as it is."
} else {
    $text = [System.IO.File]::ReadAllText((Join-Path $target $template))
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($handoffPath, $text.Replace('<session>', $Name), $utf8)
    Write-Output "Made $handoff from the template (uncommitted; commit it on $branch)."
}

Write-Output @"

Next steps:
  1. Open the folder in VS Code:
       code "$target"
  2. Set it up once (a worktree has no .venv or node_modules of its own):
       python -m venv .venv
       .venv\Scripts\activate
       pip install -r requirements-dev.txt
       pnpm install
  3. Add a row for "$Name" to docs\SESSIONS.md, "Active sessions", or let Claude do it.
  4. Give Claude this first message:

Read CLAUDE.md, docs/SESSIONS.md and docs/handoff/$Name.md, then docs/DESIGN.md and docs/PLAN.md. You are the "$Name" session, in the worktree $target on branch $branch. Claim or update your row in docs/SESSIONS.md, follow "Parallel sessions" in CLAUDE.md, and edit only the files your session owns. Tell me your plan before changing code.
"@
