@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Build script for scanner404 using Nuitka
REM - Outputs everything under .\build
REM - Default mode is standalone
REM - For standalone builds, creates an Inno Setup installer EXE
REM - Optional mode is onefile

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
for %%I in ("%ENTRY%") do set "ENTRY_BASENAME=%%~nI"
set "ISS_FILE=installer\scanner404.iss"
set "ICON_PNG=scanner404\assets\logo.png"
set "ICON_ICO=scanner404\assets\logo.ico"
set "INSTALLER_OUTDIR=%OUTDIR%\installer"
set "INSTALLER_BASENAME=%APPNAME%-setup"

REM Installer toggle for standalone mode: 1 (default) or 0
if not defined BUILD_INSTALLER set "BUILD_INSTALLER=1"

REM Auto-install Inno Setup if missing: 1 (default) or 0
if not defined AUTO_INSTALL_INNO set "AUTO_INSTALL_INNO=1"

REM Build mode: standalone (default) or onefile
if not defined BUILD_MODE set "BUILD_MODE=standalone"

if /I "%BUILD_MODE%"=="standalone" (
    set "MODE_FLAGS=--standalone"
    set "DIST_DIR=%OUTDIR%\%ENTRY_BASENAME%.dist"
    set "EXE_PATH=%OUTDIR%\%ENTRY_BASENAME%.dist\%APPNAME%.exe"
    set "SETUP_EXE=%INSTALLER_OUTDIR%\%INSTALLER_BASENAME%.exe"
) else if /I "%BUILD_MODE%"=="onefile" (
    set "MODE_FLAGS=--onefile"
    set "EXE_PATH=%OUTDIR%\%APPNAME%.exe"
    set "DIST_DIR="
    set "SETUP_EXE="
) else (
    echo [ERROR] Invalid BUILD_MODE "%BUILD_MODE%". Use "standalone" or "onefile".
    exit /b 1
)

REM Windows version/resource metadata (edit these for your release)
set "COMPANY=Brian Carlo"
set "PRODUCT_NAME=Scanner404"
set "FILE_DESCRIPTION=Scanner404 desktop scanner utility"
set "PRODUCT_VERSION=1.0.0"
set "FILE_VERSION=1.0.0.0"
set "COPYRIGHT=Copyright (c) 2026 Brian Carlo"

REM Signing mode: self or none
if not defined SIGN_MODE (
    if defined CI (
        set "SIGN_MODE=none"
    ) else (
        set "SIGN_MODE=self"
    )
)
set "CERT_SUBJECT=Scanner404 Self-Signed"

set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=powershell"

if not exist "%ENTRY%" (
    echo [ERROR] Entry file "%ENTRY%" not found in %CD%.
    exit /b 1
)

set "ICON_FLAGS="
set "INSTALLER_ICON_DEFINE="
if exist "%ICON_ICO%" (
    set "ICON_FLAGS=!ICON_FLAGS! --windows-icon-from-ico=%ICON_ICO%"
    set "INSTALLER_ICON_DEFINE=/DSetupIconFile=%CD%\%ICON_ICO%"
) else (
    echo [WARN] Icon file "%ICON_ICO%" not found.
    echo [WARN] EXE and installer will use default icon. Add a .ico file to enable branding.
)

if exist "%ICON_PNG%" (
    set "ICON_FLAGS=!ICON_FLAGS! --include-data-files=%ICON_PNG%=scanner404/assets/logo.png"
)

echo [INFO] Building "%ENTRY%" with Nuitka...
echo [INFO] Output directory: %OUTDIR%
echo [INFO] Build mode: %BUILD_MODE%

python -m nuitka ^
    %MODE_FLAGS% ^
    --windows-console-mode=disable ^
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
    %ICON_FLAGS% ^
    "%ENTRY%"

if errorlevel 1 (
    echo [ERROR] Build failed.
    exit /b 1
)

if /I "%BUILD_MODE%"=="standalone" (
    if not exist "%EXE_PATH%" if exist "%OUTDIR%\%APPNAME%.dist\%APPNAME%.exe" (
        set "DIST_DIR=%OUTDIR%\%APPNAME%.dist"
        set "EXE_PATH=%DIST_DIR%\%APPNAME%.exe"
    )
)

if not exist "%EXE_PATH%" (
    echo [ERROR] Expected executable not found: %EXE_PATH%
    exit /b 1
)

if /I "%SIGN_MODE%"=="self" (
    echo [INFO] Self-signing executable with a local certificate...

    "%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
        "if(-not (Get-PSDrive -Name Cert -PSProvider Certificate -ErrorAction SilentlyContinue)){ exit 10 };" ^
        "if(-not (Get-Command Set-AuthenticodeSignature -ErrorAction SilentlyContinue)){ exit 11 };" ^
        "if(-not (Get-Command New-SelfSignedCertificate -ErrorAction SilentlyContinue)){ exit 12 };" ^
        "exit 0"

    set "SIGN_PRECHECK_RC=%ERRORLEVEL%"
    if "%SIGN_PRECHECK_RC%"=="10" (
        echo [WARN] Certificate provider is unavailable in this shell. Skipping self-sign.
    ) else if "%SIGN_PRECHECK_RC%"=="11" (
        echo [WARN] Set-AuthenticodeSignature is unavailable. Skipping self-sign.
    ) else if "%SIGN_PRECHECK_RC%"=="12" (
        echo [WARN] New-SelfSignedCertificate is unavailable. Skipping self-sign.
    ) else (
    "%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
        "$subject='CN=%CERT_SUBJECT%';" ^
        "$store='Cert:\CurrentUser\My';" ^
        "$cert=Get-ChildItem $store | Where-Object { $_.Subject -eq $subject -and $_.HasPrivateKey } | Sort-Object NotAfter -Descending | Select-Object -First 1;" ^
        "if(-not $cert){ $cert=New-SelfSignedCertificate -Type CodeSigningCert -Subject $subject -CertStoreLocation $store -NotAfter (Get-Date).AddYears(3) };" ^
        "$result=Set-AuthenticodeSignature -FilePath '%EXE_PATH%' -Certificate $cert;" ^
        "if(-not $result.SignerCertificate){ Write-Error 'Failed to sign executable.'; exit 1 };" ^
        "$cerPath='%OUTDIR%\%APPNAME%-selfsign.cer';" ^
        "Export-Certificate -Cert $cert -FilePath $cerPath -Force | Out-Null;"

        if errorlevel 1 (
            echo [WARN] Self-sign step failed. Continuing without signature.
        ) else (
            echo [INFO] Self-sign complete.
            echo [INFO] Certificate exported to: %OUTDIR%\%APPNAME%-selfsign.cer
            echo [INFO] To trust this certificate locally ^(CurrentUser^):
            echo        certutil -user -addstore TrustedPublisher "%OUTDIR%\%APPNAME%-selfsign.cer"
            echo        certutil -user -addstore Root "%OUTDIR%\%APPNAME%-selfsign.cer"
        )
    )
) else (
    echo [INFO] Signing skipped. SIGN_MODE=%SIGN_MODE%
)

if /I "%BUILD_MODE%"=="standalone" (
    if /I "%BUILD_INSTALLER%"=="1" (
        if not exist "%ISS_FILE%" (
            echo [ERROR] Inno Setup script not found: %ISS_FILE%
            exit /b 1
        )

        set "ISCC_EXE="
        where iscc >nul 2>nul && set "ISCC_EXE=iscc"
        if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
        if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
        if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

        if not defined ISCC_EXE (
            if /I "%AUTO_INSTALL_INNO%"=="1" (
                echo [INFO] Inno Setup compiler not found. Attempting automatic install...

                where winget >nul 2>nul
                if not errorlevel 1 (
                    echo [INFO] Installing Inno Setup via winget...
                    winget install --id JRSoftware.InnoSetup -e --silent --accept-package-agreements --accept-source-agreements
                ) else (
                    where choco >nul 2>nul
                    if not errorlevel 1 (
                        echo [INFO] Installing Inno Setup via Chocolatey...
                        choco install innosetup -y --no-progress
                    ) else (
                        echo [WARN] Neither winget nor choco is available for automatic install.
                    )
                )

                REM Re-detect after install attempt.
                set "ISCC_EXE="
                where iscc >nul 2>nul && set "ISCC_EXE=iscc"
                if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
                if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
                if not defined ISCC_EXE if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
            )
        )

        if not defined ISCC_EXE (
            echo [ERROR] Inno Setup compiler ^(ISCC.exe^) not found.
            echo         Install Inno Setup 6 or add ISCC.exe to PATH.
            echo         You can disable auto-install with AUTO_INSTALL_INNO=0.
            echo         To skip installer generation, set BUILD_INSTALLER=0.
            exit /b 1
        )

        if not exist "%INSTALLER_OUTDIR%" mkdir "%INSTALLER_OUTDIR%" >nul 2>nul
        if exist "%SETUP_EXE%" del /f /q "%SETUP_EXE%" >nul 2>nul
        set "DIST_DIR_ABS=%CD%\%DIST_DIR%"
        set "INSTALLER_OUTDIR_ABS=%CD%\%INSTALLER_OUTDIR%"

        echo [INFO] Building Inno Setup installer...
        echo [INFO] Using ISCC: !ISCC_EXE!
        if defined INSTALLER_ICON_DEFINE (
            "!ISCC_EXE!" /Qp ^
                "/DAppName=%PRODUCT_NAME%" ^
                "/DAppVersion=%PRODUCT_VERSION%" ^
                "/DPublisher=%COMPANY%" ^
                "/DSourceDir=!DIST_DIR_ABS!" ^
                "/DOutputDir=!INSTALLER_OUTDIR_ABS!" ^
                "/DOutputBaseFilename=%INSTALLER_BASENAME%" ^
                "!INSTALLER_ICON_DEFINE!" ^
                "%ISS_FILE%"
        ) else (
            "!ISCC_EXE!" /Qp ^
                "/DAppName=%PRODUCT_NAME%" ^
                "/DAppVersion=%PRODUCT_VERSION%" ^
                "/DPublisher=%COMPANY%" ^
                "/DSourceDir=!DIST_DIR_ABS!" ^
                "/DOutputDir=!INSTALLER_OUTDIR_ABS!" ^
                "/DOutputBaseFilename=%INSTALLER_BASENAME%" ^
                "%ISS_FILE%"
        )

        if errorlevel 1 (
            echo [ERROR] Installer build failed.
            exit /b 1
        )

        if /I "%SIGN_MODE%"=="self" if exist "%SETUP_EXE%" (
            echo [INFO] Self-signing installer executable...
            "%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -Command ^
                "$subject='CN=%CERT_SUBJECT%';" ^
                "$store='Cert:\CurrentUser\My';" ^
                "$cert=Get-ChildItem $store | Where-Object { $_.Subject -eq $subject -and $_.HasPrivateKey } | Sort-Object NotAfter -Descending | Select-Object -First 1;" ^
                "if($cert){ Set-AuthenticodeSignature -FilePath '%SETUP_EXE%' -Certificate $cert | Out-Null }"

            if errorlevel 1 (
                echo [WARN] Installer self-sign failed. Continuing without installer signature.
            )
        )
    ) else (
        echo [INFO] Installer generation skipped. BUILD_INSTALLER=%BUILD_INSTALLER%
    )

    if /I "%BUILD_INSTALLER%"=="1" if not exist "%SETUP_EXE%" (
        echo [ERROR] Expected installer not found: %SETUP_EXE%
        exit /b 1
    )

    if /I "%BUILD_INSTALLER%"=="1" echo [INFO] Installer ready: %SETUP_EXE%
)

echo [SUCCESS] Build complete.
echo          Executable file:   %EXE_PATH%
if /I "%BUILD_MODE%"=="standalone" if /I "%BUILD_INSTALLER%"=="1" echo          Installer file:    %SETUP_EXE%
exit /b 0
