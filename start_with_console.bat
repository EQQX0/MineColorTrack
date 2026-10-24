@echo off
rem Same as start.bat but keeps a console open so error messages are visible.
cd /d "%~dp0"
py -3 run.py %*
pause
