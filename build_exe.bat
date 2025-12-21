@echo off
REM Build script for BlockyMarketMaker Windows executable
REM Run this from the project root directory

echo ========================================
echo BlockyMarketMaker Build Script
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Install project dependencies
echo.
echo Installing project dependencies...
pip install -r requirements.txt

REM Build the executable
echo.
echo Building executable...
pyinstaller blocky.spec --clean

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
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
echo To distribute:
echo 1. Copy dist\BlockyMarketMaker.exe
echo 2. Copy config.yaml (as template)
echo 3. User runs the exe, completes setup
echo.
pause
