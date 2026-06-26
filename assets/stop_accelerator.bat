@echo off
echo Stopping Talend Migration Accelerator...
taskkill /f /im python.exe /fi "WINDOWTITLE eq Talend Migration Accelerator" >nul 2>&1
taskkill /f /im streamlit.exe >nul 2>&1
echo Done.
pause
