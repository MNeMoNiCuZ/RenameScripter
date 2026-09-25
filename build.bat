@echo off
:: Build a standalone RenameScripter.exe into dist\RenameScripter (see build.py --help)
cd /d %~dp0
if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python build.py %*
if errorlevel 1 (
    echo.
    echo Build FAILED.
)
pause
