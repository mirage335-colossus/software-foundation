param([string]$MinimumLinker = '')
$ErrorActionPreference = 'Stop'
$chosen = & (Join-Path $PSScriptRoot 'select-windows-toolchain.ps1') -MinimumLinker $MinimumLinker
$setup = Join-Path $chosen.InstallationPath 'VC/Auxiliary/Build/vcvars64.bat'
$environment = & cmd.exe /d /s /c "`"$setup`" $($chosen.WindowsSdk) -vcvars_ver=$($chosen.ToolsVersion) >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'Pinned MSVC environment setup failed' }
foreach ($line in $environment) {
    if ($line -match '^([^=]+)=(.*)$') {
        $name = $Matches[1]
        $value = $Matches[2]
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        if ($env:GITHUB_ENV) { "$name=$value" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append }
    }
}
# Record exact selected tool versions so a consuming job can require a sufficiently
# recent linker. A dependency base does not include Microsoft installer media.
$chosen | ConvertTo-Json -Compress
