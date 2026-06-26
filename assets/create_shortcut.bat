@echo off
title Create TMA Desktop Shortcut
cd /d "%~dp0\.."
set "APP_DIR=%cd%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([System.IO.Path]::Combine($env:USERPROFILE, 'Desktop', 'Talend Migration Accelerator.lnk')); $s.TargetPath = '%APP_DIR%\assets\start_accelerator.bat'; $s.WorkingDirectory = '%APP_DIR%'; $s.IconLocation = '%APP_DIR%\assets\tma.ico,0'; $s.WindowStyle = 1; $s.Description = 'Talend Migration Accelerator'; $s.Save(); Write-Host 'Shortcut created on Desktop.'"

echo.
echo Done! Check your Desktop for "Talend Migration Accelerator"
pause
