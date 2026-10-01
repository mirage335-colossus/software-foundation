$ErrorActionPreference = 'Stop'
$selector = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$install = & $selector -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $install) { throw 'A supported MSVC x64 toolchain is required' }
$setup = Join-Path $install 'VC/Auxiliary/Build/vcvars64.bat'
# Read environment output from the known toolchain script; never evaluate it as code.
$environment = & cmd.exe /d /s /c "`"$setup`" >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'MSVC environment setup failed' }
foreach ($line in $environment) {
    if ($line -match '^([^=]+)=(.*)$') {
        $name = $Matches[1]
        $value = $Matches[2]
        if ($name -notmatch '^=') {
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
            if ($env:GITHUB_ENV) { "$name=$value" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append }
        }
    }
}
