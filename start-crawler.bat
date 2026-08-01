@echo off
REM Komichi Crawler + Tunnel 一键启动
REM 双击此文件即可启动 crawler-daemon 和 cloudflared 隧道
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0start-crawler.ps1" %*
pause
