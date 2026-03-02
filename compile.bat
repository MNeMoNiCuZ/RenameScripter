@echo off
cd /d %~dp0
call venv\Scripts\activate

echo Installing PyInstaller if needed...
pip install pyinstaller

echo.
echo Compiling RenameScripter...
pyinstaller --noconfirm --onefile --windowed ^
    --icon "Settings\icon.ico" ^
    --name "RenameScripter" ^
    --add-data "Settings\icon.ico;Settings" ^
    RenameScripter.py

echo.
echo Creating distribution folder...
if not exist "dist\Scripts" mkdir "dist\Scripts"
if not exist "dist\Settings" mkdir "dist\Settings"

echo Copying Scripts folder (not baked in)...
xcopy /E /Y /I "Scripts" "dist\Scripts"

echo Copying Settings...
copy /Y "Settings\config.ini" "dist\Settings\" 2>nul
copy /Y "Settings\icon.ico" "dist\Settings\"

echo.
echo Done! Your compiled app is in the "dist" folder.
echo Make sure the Scripts folder stays next to RenameScripter.exe
pause
