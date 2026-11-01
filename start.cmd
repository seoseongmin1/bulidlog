@echo off
rem PowerShell 스크립트 실행 제한과 상관없이 start.ps1을 실행한다.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
