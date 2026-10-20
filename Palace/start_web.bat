@echo off
cd /d "%~dp0"
echo Starting Palace at http://localhost:5599/index.html  (close this window to stop)
start "" http://localhost:5599/index.html
where python >nul 2>nul && (python -m http.server 5599 & goto :eof)
where py >nul 2>nul && (py -m http.server 5599 & goto :eof)
if exist "%USERPROFILE%\.local\bin\python3.14.exe" ("%USERPROFILE%\.local\bin\python3.14.exe" -m http.server 5599 & goto :eof)
echo Python was not found. Install Python or use the VS Code Live Server extension.
pause
