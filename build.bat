@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Build script for scanner404 using Nuitka
REM - Outputs everything under .\build
REM - Produces a single executable build\scanner404.exe

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python is not available on PATH.
    exit /b 1
)

python -m nuitka --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Nuitka is not available in this Python environment.
    echo         Install/activate the environment where Nuitka is installed, then retry.
    exit /b 1
)

set "ENTRY=main.py"
set "OUTDIR=build"
set "APPNAME=scanner404"

REM Windows version/resource metadata (edit these for your release)
set "COMPANY=Brian Carlo"
set "PRODUCT_NAME=Scanner404"
set "FILE_DESCRIPTION=Scanner404 desktop scanner utility"
set "PRODUCT_VERSION=1.0.0"
set "FILE_VERSION=1.0.0.0"
set "COPYRIGHT=Copyright (c) 2026 Brian Carlo"

REM Signing mode: self or none
if not defined SIGN_MODE set "SIGN_MODE=self"
set "CERT_SUBJECT=Scanner404 Self-Signed"

if not exist "%ENTRY%" (
    echo [ERROR] Entry file "%ENTRY%" not found in %CD%.
    exit /b 1
)

echo [INFO] Building "%ENTRY%" with Nuitka...
echo [INFO] Output directory: %OUTDIR%

python -m nuitka ^
    --onefile ^
    --enable-plugin=tk-inter ^
    --follow-imports ^
    --assume-yes-for-downloads ^
    --remove-output ^
    --output-dir="%OUTDIR%" ^
    --output-filename="%APPNAME%" ^
    --company-name="%COMPANY%" ^
    --product-name="%PRODUCT_NAME%" ^
    --file-description="%FILE_DESCRIPTION%" ^
    --product-version="%PRODUCT_VERSION%" ^
    --file-version="%FILE_VERSION%" ^
    --copyright="%COPYRIGHT%" ^
    "%ENTRY%"

if errorlevel 1 (
    echo [ERROR] Build failed.
    exit /b 1
)

set "EXE_PATH=%OUTDIR%\%APPNAME%.exe"

if /I "%SIGN_MODE%"=="self" (
    echo [INFO] Self-signing executable with a local certificate...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$subject='CN=%CERT_SUBJECT%';" ^
        "$store='Cert:\CurrentUser\My';" ^
        "$cert=Get-ChildItem $store | Where-Object { $_.Subject -eq $subject -and $_.HasPrivateKey } | Sort-Object NotAfter -Descending | Select-Object -First 1;" ^
        "if(-not $cert){ $cert=New-SelfSignedCertificate -Type CodeSigningCert -Subject $subject -CertStoreLocation $store -NotAfter (Get-Date).AddYears(3) };" ^
        "$result=Set-AuthenticodeSignature -FilePath '%EXE_PATH%' -Certificate $cert;" ^
        "if(-not $result.SignerCertificate){ Write-Error 'Failed to sign executable.'; exit 1 };" ^
        "$cerPath='%OUTDIR%\%APPNAME%-selfsign.cer';" ^
        "Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null;"

    if errorlevel 1 (
        echo [ERROR] Self-sign step failed.
        exit /b 1
    )

    echo [INFO] Self-sign complete.
    echo [INFO] Certificate exported to: %OUTDIR%\%APPNAME%-selfsign.cer
    echo [INFO] To trust this certificate locally ^(CurrentUser^):
    echo        certutil -user -addstore TrustedPublisher "%OUTDIR%\%APPNAME%-selfsign.cer"
    echo        certutil -user -addstore Root "%OUTDIR%\%APPNAME%-selfsign.cer"
) else (
    echo [INFO] Signing skipped. SIGN_MODE=%SIGN_MODE%
)

echo [SUCCESS] Build complete.
echo          Executable file:   %EXE_PATH%
exit /b 0
