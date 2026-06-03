@echo off
cd /d "%~dp0"
title Job Lead Tool  -  keep this window open
echo ============================================================
echo   JOB LEAD TOOL
echo ============================================================
echo.
echo   Starting the app...
echo   Your web browser will open in a few seconds.
echo.
echo   KEEP THIS BLACK WINDOW OPEN while you use the app.
echo   To stop the app later, just close this window.
echo.
echo ============================================================
echo.
start "" /min cmd /c "timeout /t 3 >nul & explorer http://localhost:8000"
".venv\Scripts\python.exe" -m uvicorn backend.main:app
echo.
echo The app has stopped. You can close this window.
pause
