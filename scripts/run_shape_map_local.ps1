param(
    [Parameter(Mandatory = $true)]
    [string]$Config,

    [switch]$AssembleOnly,
    [switch]$DemuxOnly,
    [switch]$SkipDemux
)

$ErrorActionPreference = "Stop"

$configPath = Resolve-Path -LiteralPath $Config
$scriptPath = Resolve-Path -LiteralPath "$PSScriptRoot\shape_map_local.py"

$wslConfig = (wsl --exec wslpath -a "$configPath").Trim()
$wslScript = (wsl --exec wslpath -a "$scriptPath").Trim()

$argsList = @("python3", "$wslScript", "$wslConfig")
if ($AssembleOnly) {
    $argsList += "--assemble-only"
}
if ($DemuxOnly) {
    $argsList += "--demux-only"
}
if ($SkipDemux) {
    $argsList += "--skip-demux"
}

wsl --exec @argsList
