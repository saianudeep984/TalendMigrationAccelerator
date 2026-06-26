@echo off
title Talend Migration Accelerator
echo ================================================
echo  Talend Migration Accelerator - Starting...
echo ================================================
echo.

cd /d "%~dp0\.."

echo [1/3] Installing dependencies...
python.exe -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Is Python installed?
    pause
    exit /b 1
)

echo [2/3] Dependencies ready.
echo [3/3] Launching Streamlit app...
echo.
echo Open your browser at: http://localhost:8501
echo Press Ctrl+C to stop the server.
echo.

python.exe -m streamlit run app/ui/streamlit_app.py --server.port 8501 --server.headless false

pause
