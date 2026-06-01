param(
    [string]$Archive = ".\downloads\shapemapper2-2.3.tar.gz",
    [string]$InstallDir = "~/tools"
)

$ErrorActionPreference = "Stop"

$archivePath = Resolve-Path -LiteralPath $Archive
$wslArchive = (wsl --exec wslpath -a "$archivePath").Trim()

wsl --exec bash -lc "set -e; mkdir -p $InstallDir; rm -rf $InstallDir/shapemapper2-2.3; tar -xzf '$wslArchive' -C $InstallDir; '$InstallDir/shapemapper2-2.3/shapemapper' --version"
