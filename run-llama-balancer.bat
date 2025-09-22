
@echo off

if not exist "%~dp0potable-cmd.bat" (
    echo potable-cmd.bat not found. Downloading...
    curl -L -o "%~dp0potable-cmd.bat" "https://raw.githubusercontent.com/issixx/llama-balancer/main/potable-cmd.bat"
    if ERRORLEVEL 1 goto :ERROR
)
call "%~dp0potable-cmd.bat"
if ERRORLEVEL 1 goto :ERROR

python %~dp0llama-balancer-server.py

echo ####################
echo #   %~n0 success
echo ####################
echo success
exit /b 0

:ERROR
	echo ###################
    echo #   %~n0 failure
	echo ###################
	pause
exit /b 1
