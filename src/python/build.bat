@echo off
echo Building OAK Controller...

REM Install dependencies
pip install -r requirements.txt

REM Build with PyInstaller
pyinstaller OAKController.spec

echo.
echo Build complete! Output is in dist/OAK Controller.exe
pause