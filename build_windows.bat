@echo off
REM Build script for BlockyMarketMaker Windows executable (System Tray version)
REM Run this from the project root directory

echo ========================================
echo BlockyMarketMaker Windows Build
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/5] Checking Python version...
python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>nul
if errorlevel 1 (
    echo WARNING: Python 3.11+ is recommended
    echo Current version:
    python --version
    echo.
)

REM Install project dependencies
echo.
echo [2/5] Installing project dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Install/upgrade PyInstaller
echo.
echo [3/5] Installing PyInstaller...
pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller
    pause
    exit /b 1
)

REM Clean previous build
echo.
echo [4/5] Cleaning previous build...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

REM Build the executable
echo.
echo [5/5] Building executable...
python -m PyInstaller blocky_windows.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ========================================
    echo ERROR: Build failed!
    echo ========================================
    echo.
    echo Common fixes:
    echo - Make sure all dependencies are installed
    echo - Check for syntax errors in Python files
    echo - Try running: pip install --upgrade pyinstaller
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build successful!
echo ========================================
echo.
echo Executable location: dist\BlockyMarketMaker.exe
echo.
echo Features:
echo   - No console window (clean!)
echo   - System tray icon for control
echo   - Dashboard opens in browser automatically
echo   - Setup wizard on first run
echo.
echo To distribute:
echo   - Users only need BlockyMarketMaker.exe
echo   - No Python installation required
echo.
pause
