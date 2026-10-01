param([Parameter(Mandatory=$true)][string]$Script, [Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)
$ErrorActionPreference = 'Stop'
$argList = @('-e', 'bash', '-lc', 'cd ~/proofsmith && source ~/.venvs/proofsmith/bin/activate 2>/dev/null; bash "$0" "$@"', $Script) + $Rest
& wsl.exe @argList
exit $LASTEXITCODE
