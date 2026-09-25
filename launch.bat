@echo off
rem Starts the voice changer: launch.bat [-Preset vctk-p238] [-NoCudaGraph] [-ListDevices] [-ListPresets]
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%
