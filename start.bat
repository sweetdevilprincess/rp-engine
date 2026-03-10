@echo off
REM RP Engine — Setup & Launch Script (Windows)
REM Usage: start.bat [--rebuild]

setlocal enabledelayedexpansion
cd /d "%~dp0"

set REBUILD=0
for %%a in (%*) do (
    if "%%a"=="--rebuild" set REBUILD=1
)

REM ── Check Python ──────────────────────────────────────────
set PYTHON=
for %%c in (python py) do (
    where %%c >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%v in ('%%c -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do (
            for /f "tokens=1,2 delims=." %%a in ("%%v") do (
                if %%a geq 3 if %%b geq 12 (
                    set PYTHON=%%c
                    echo [OK] Found %%c %%v
                    goto :python_found
                )
            )
        )
    )
)
echo [ERROR] Python 3.12+ is required. Install from https://python.org
exit /b 1
:python_found

REM ── Create venv if needed ─────────────────────────────────
if not exist ".venv" (
    echo -- Creating virtual environment...
    %PYTHON% -m venv .venv
)

REM Activate venv
call .venv\Scripts\activate.bat
echo [OK] Virtual environment active

REM ── Install Python deps ───────────────────────────────────
echo -- Installing Python dependencies...
pip install -q -e . 2>nul

REM ── Build frontend ────────────────────────────────────────
if %REBUILD% equ 1 goto :build_frontend
if not exist "frontend\build\index.html" goto :build_frontend
echo [OK] Frontend build exists (use --rebuild to force)
goto :skip_build

:build_frontend
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is required to build the frontend. Install from https://nodejs.org
    exit /b 1
)
echo -- Building frontend...
cd frontend
call npm install --silent 2>nul
call npm run build 2>nul
cd ..
echo [OK] Frontend built

:skip_build

REM ── Start server ──────────────────────────────────────────
if not defined PORT set PORT=3000
echo.
echo ============================================
echo   RP Engine starting on http://localhost:%PORT%
echo ============================================
echo.

REM Open browser after server is ready (polls in background)
start /b "" %PYTHON% open_browser.py %PORT%

rp-engine --port %PORT%
