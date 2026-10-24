@echo off
cd /d "%~dp0"
echo Installing ColorAssist requirements...
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Install failed. Make sure Python 3.10 or newer is installed from python.org
  echo and that "Add python.exe to PATH" / the py launcher was ticked during setup.
  pause
  exit /b 1
)
echo.
echo Done. Double-click start.bat to run ColorAssist.
pause
