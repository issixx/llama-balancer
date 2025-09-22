
@echo off

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
