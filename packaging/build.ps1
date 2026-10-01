$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 x64 is required on the build computer.' }
}
$PythonExe = Join-Path $PWD '.venv\Scripts\python.exe'
& $PythonExe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
& $PythonExe -m pip install '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$env:QT_QPA_PLATFORM = 'offscreen'
& $PythonExe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
Remove-Item Env:QT_QPA_PLATFORM
& $PythonExe -m PyInstaller --clean --noconfirm packaging/CredentialStudio.spec
if ($LASTEXITCODE -ne 0) { throw 'Application packaging failed' }
& $PythonExe packaging/collect_notices.py
if ($LASTEXITCODE -ne 0) { throw 'Third-party notices collection failed' }
$SmokeProcess = Start-Process -FilePath 'dist\CredentialStudio\CredentialStudio.exe' -ArgumentList '--smoke-test' -Wait -PassThru
if ($SmokeProcess.ExitCode -ne 0) { throw 'Packaged application smoke test failed' }
$CompilerPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $CompilerPath)) { throw 'Install Inno Setup 6 on the build computer, then rerun.' }
& $CompilerPath packaging/installer.iss
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
Write-Host 'Installer: dist\installer\CredentialStudio-0.2.0-Setup-x64.exe'
