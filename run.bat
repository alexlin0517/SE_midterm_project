@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ==============================================================================
echo            Manuscript Review System (FastAPI + PostgreSQL + Jinja2)
echo ==============================================================================

if not exist "%~dp0venv\Scripts\python.exe" goto NO_VENV

echo [Environment] Project virtual environment found at .\venv
echo [Startup] Starting Uvicorn using local virtual environment...
echo.
echo Server URL: http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
echo ==============================================================================
echo.
"%~dp0venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
goto FINISH

:NO_VENV
echo [WARNING] Local virtual environment .\venv not found.
echo [Startup] Attempting to start with system Python...
echo.
echo Server URL: http://127.0.0.1:8000
echo Press Ctrl+C to stop the server.
echo ==============================================================================
echo.
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

:FINISH
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Server stopped with error code %ERRORLEVEL%.
    echo.
)

pause
