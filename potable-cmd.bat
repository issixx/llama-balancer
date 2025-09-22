:: Copyright 2025 issixx. All Rights Reserved.

@echo off

:: Do nothing if called recursively
if "%POTABLE_CMD_CALLED%" equ "1" exit /b 0
set POTABLE_CMD_CALLED=1

:: Prevent output from clearing when entering venv
chcp 65001 > NUL

::###################################################################################
:: feature settings
::###################################################################################

:: Set to 1 to enable each feature
if "%ENABLE_GIT%"         equ "" set ENABLE_GIT=1
if "%ENABLE_CMAKE%"       equ "" set ENABLE_CMAKE=0
if "%ENABLE_PYTHON%"      equ "" set ENABLE_PYTHON=1
if "%ENABLE_PYTHON_VENV%" equ "" set ENABLE_PYTHON_VENV=0
if "%ENABLE_CUDA%"        equ "" set ENABLE_CUDA=0
if "%ENABLE_VULKAN%"      equ "" set ENABLE_VULKAN=0
if "%ENABLE_CHROME%"      equ "" set ENABLE_CHROME=0
if "%ENABLE_FFMPEG%"      equ "" set ENABLE_FFMPEG=0
if "%ENABLE_NODEJS%"      equ "" set ENABLE_NODEJS=0
if "%ENABLE_GO%"          equ "" set ENABLE_GO=0
if "%ENABLE_CHECKOUT_LLAMA_BALANCER%"     equ "" set ENABLE_CHECKOUT_LLAMA_BALANCER=1

::###################################################################################
:: workspace settings
::###################################################################################
if "%CUR_DIR%" equ "" set CUR_DIR=%~dp0

:: Search parent folders for the workspace folder
if "%SEARCH_PARENT_WORKSPACE%" equ "" set SEARCH_PARENT_WORKSPACE=0
if "%BASE_DIR_NAME%"        equ "" (for %%A in ("%CUR_DIR%.") do set BASE_DIR_NAME=%%~nA)
if "%WORKSPACE_NAME%"       equ "" set WORKSPACE_NAME=workspace
set WORKSPACE_ROOT_DEFAULT=%CUR_DIR%%WORKSPACE_NAME%
if "%WORKSPACE_ROOT%"       equ "" set WORKSPACE_ROOT=%WORKSPACE_ROOT_DEFAULT%
:: Use this shorter path if %WORKSPACE_ROOT% is too long and causes build failures
if "%WORKSPACE_SHORT_ROOT%" equ "" set WORKSPACE_SHORT_ROOT=%USERPROFILE%\%BASE_DIR_NAME%\%WORKSPACE_NAME%
if "%LIB_DIR_NAME%"         equ "" set LIB_DIR_NAME=lib
if "%PYTHON_VENV_DIR_NAME%" equ "" set PYTHON_VENV_DIR_NAME=venv

::###################################################################################
:: installer settings
::###################################################################################
if "%POTABLE_GIT_URL%"        equ "" set POTABLE_GIT_URL=https://github.com/git-for-windows/git/releases/download/v2.47.0.windows.2/PortableGit-2.47.0.2-64-bit.7z.exe
::if "%POTABLE_CMAKE_URL%"    equ "" set POTABLE_CMAKE_URL=https://github.com/Kitware/CMake/releases/download/v3.30.5/cmake-3.30.5-windows-x86_64.zip
if "%POTABLE_CMAKE_URL%"      equ "" set POTABLE_CMAKE_URL=https://github.com/Kitware/CMake/releases/download/v3.28.6/cmake-3.28.6-windows-x86_64.zip
::if "%POTABLE_PYTHON_URL%"   equ "" set POTABLE_PYTHON_URL=https://www.python.org/ftp/python/3.13.0/python-3.13.0-embed-amd64.zip
if "%POTABLE_PYTHON_URL%"     equ "" set POTABLE_PYTHON_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9-embed-amd64.zip
if "%POTABLE_PYTHON_PIP_URL%" equ "" set POTABLE_PYTHON_PIP_URL=https://bootstrap.pypa.io/get-pip.py
::if "%POTABLE_PYTHON_REQUIREMENT_MODULES%" equ "" set POTABLE_PYTHON_REQUIREMENT_MODULES=blinker==1.7.0 selenium-wire==5.1.0 selenium==4.23.1 requests setuptools packaging
if "%CUDA_URL%"               equ "" set CUDA_URL=https://developer.download.nvidia.com/compute/cuda/12.6.2/local_installers/cuda_12.6.2_560.94_windows.exe
if "%VULKAN_URL%"             equ "" set VULKAN_URL=https://sdk.lunarg.com/sdk/download/1.3.296.0/windows/VulkanSDK-1.3.296.0-Installer.exe
if "%POTABLE_CHROME_URL%"     equ "" set POTABLE_CHROME_URL=https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.168/win64/chrome-win64.zip
if "%POTABLE_CHROME_DRIVER_URL%" equ "" set POTABLE_CHROME_DRIVER_URL=https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.168/win64/chromedriver-win64.zip
if "%POTABLE_FFMPEG_URL%"     equ "" set POTABLE_FFMPEG_URL=https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip
if "%POTABLE_NODEJS_URL%"     equ "" set POTABLE_NODEJS_URL=https://nodejs.org/download/release/latest-v20.x/node-v20.19.5-win-x64.zip
if "%POTABLE_GO_URL%"         equ "" set POTABLE_GO_URL=https://go.dev/dl/go1.25.1.windows-amd64.zip
::if "%POTABLE_NODEJS_URL%"     equ "" set POTABLE_NODEJS_URL=https://nodejs.org/dist/v22.18.0/node-v22.18.0-win-x64.zip

::###################################################################################
:: etc settings
::###################################################################################

:: The build succeeded with up to 107 characters in the current environment,
:: but it is set to 100 as a precaution.
if "%CUR_DIR_LEN_MAX%" equ "" set CUR_DIR_LEN_MAX=100

:: Set to 1 to use pre-installed exe
if "%USE_SYSTEM_EXE%" equ "" set USE_SYSTEM_EXE=0

:: Use venv if system exe is used
if "%USE_SYSTEM_EXE%" equ "1" (
    set ENABLE_PYTHON_VENV=1
)

::###################################################################################
:: check path length and deside workspace path
::###################################################################################

:: Check if the current directory path is too long to avoid build failure
:: and decide the workspace path
call :DESIDE_WORKSPACE_ROOT_LEN
if ERRORLEVEL 1 goto :ERROR

::###################################################################################
:: main
::###################################################################################
set LIB_DIR=%WORKSPACE_ROOT%\%LIB_DIR_NAME%

:: make lib directory
if not exist "%LIB_DIR%\" ( mkdir "%LIB_DIR%" )

if "%ENABLE_GIT%" equ "1" (
    call :ACTIVATE_GIT
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_CMAKE%" equ "1" (
    call :ACTIVATE_CMAKE
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_PYTHON%" equ "1" (
    call :ACTIVATE_PYTHON
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_CUDA%" equ "1" (
    call :ACTIVATE_CUDA
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_VULKAN%" equ "1" (
    call :ACTIVATE_VULKAN
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_CHROME%" equ "1" (
    call :ACTIVATE_CHROME
    if ERRORLEVEL 1 goto :ERROR

    call :ACTIVATE_CHROME_DRIVER
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_FFMPEG%" equ "1" (
    call :ACTIVATE_FFMPEG
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_NODEJS%" equ "1" (
    call :ACTIVATE_NODEJS
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_GO%" equ "1" (
    call :ACTIVATE_GO
    if ERRORLEVEL 1 goto :ERROR
)

if "%ENABLE_CHECKOUT_LLAMA_BALANCER%" equ "1" (
    call :CHECKOUT_LLAMA_BALANCER
    if ERRORLEVEL 1 goto :ERROR
)

goto :SUCCESS
:ERROR
    echo ################################
    echo #   potable-cmd launch error   #
    echo ################################
    pause
exit /b 1

:SUCCESS
    echo ##################################
    echo #   potable-cmd launch success   #
    echo ##################################
    
    :: Switch to interactive mode if the script is called directly
    :: (Check if this batch filename is included in the startup command)
    echo %CMDCMDLINE:"=% | find /I "%~f0"
    if not ERRORLEVEL 1 (
        cmd /K
    )
exit /b 0

::###################################################################################
:: utility function
::###################################################################################

:: Find the exe and display the version
:WHERE_EXE
    set EXE_CMD=%1
    set VER_OPTION=%2

    :: find
    where "%EXE_CMD%" >nul 2>&1
    if ERRORLEVEL 1 (
        exit /b 1
    )

    :: get first line of where command
    for /f "tokens=1* delims=" %%A in ('where "%EXE_CMD%"') do (
        set "FIRST_LINE=%%A"
        goto :L_WHERE_EXE_0
    )
    :L_WHERE_EXE_0

    :: output exe path and version
    echo %EXE_CMD% used is located at "%FIRST_LINE%"
    if "%VER_OPTION%" neq "" (
        %EXE_CMD% %VER_OPTION%
    )
exit /b 0

:: find installed exe
:FIND_SYSTEM_EXE
    if "%USE_SYSTEM_EXE%" neq "1" exit /b 1
    call :WHERE_EXE %1 %2
    if ERRORLEVEL 1 exit /b 1
exit /b 0


:: Update the environment variable without restarting the command prompt
:UPDATE_SYSTEM_ENV
    set ENV_NAME=%1
    for /f "delims=" %%i in ('powershell -command "[System.Environment]::GetEnvironmentVariable('%ENV_NAME%', 'Machine')"') do set "%ENV_NAME%=%%i"
exit /b 0

:: Update the all argment name environment variable without restarting the command prompt
:UPDATE_SYSTEM_ENVS
    set ENV_FILETER=%1
    for /f %%i in ('powershell -command "[System.Environment]::GetEnvironmentVariables('Machine')"') do (
        echo %%i | findstr "^%ENV_FILETER%" >nul
        if not ERRORLEVEL 1 (
            call :UPDATE_SYSTEM_ENV %%i
        )
    )
exit /b 0

:: Get the length of the string
:: Usage: call :STRLEN "%~dp0" ENV_NAME
:STRLEN
    setlocal EnableDelayedExpansion
    set "_str=%~1"
    set "_count=0"

    :_STRLEN_LOOP
    if defined _str (
        set "_str=!_str:~1!"
        set /a _count+=1
        goto :_STRLEN_LOOP
    )

    ( endlocal & set "%~2=%_count%" )
exit /b 0

:: Find the parent directory of the workspace
:FIND_PARENT_DIR_WORKSPACE
    set "%~1="
    
    :: Traverse parent directories to find %WORKSPACE_NAME%
    set "SEARCH_DIR=%CUR_DIR%"
    :FIND_WORKSPACE
    
    if exist "%SEARCH_DIR%%WORKSPACE_NAME%\" (
        set "%~1=%SEARCH_DIR%%WORKSPACE_NAME%"
        exit /b 0
    )
    set "PARENT_DIR=%SEARCH_DIR:~0,-1%"
    if "%PARENT_DIR:~-1%" equ ":" exit /b 1

    for %%A in ("%PARENT_DIR%") do set "SEARCH_DIR=%%~dpA"
    if "%SEARCH_DIR%" equ "" exit /b 1
    goto :FIND_WORKSPACE
exit /b 1

:: Check if the current directory path is too long to avoid build failure
:: and decide the workspace path
:DESIDE_WORKSPACE_ROOT_LEN

    :: Use the shorter path if it already exists
    if "%WORKSPACE_SHORT_ROOT%" neq "" (
        if exist "%WORKSPACE_SHORT_ROOT%" (
            set WORKSPACE_ROOT=%WORKSPACE_SHORT_ROOT%
        )
    )

    :: if the workspace path is not set, use the default path
    if "%SEARCH_PARENT_WORKSPACE%" equ "1" (
        if "%WORKSPACE_ROOT%" equ "%WORKSPACE_ROOT_DEFAULT%" (
            call :FIND_PARENT_DIR_WORKSPACE WORKSPACE_ROOT_TEMP
        )
    )
    if "%WORKSPACE_ROOT_TEMP%" neq "" (
        set WORKSPACE_ROOT=%WORKSPACE_ROOT_TEMP%
        echo Found workspace path: %WORKSPACE_ROOT_TEMP%
    )

    :: Check if the current directory path is too long
    call :STRLEN "%WORKSPACE_ROOT%" CUR_DIR_LEN
    if %CUR_DIR_LEN% LEQ %CUR_DIR_LEN_MAX% (
        :: ok
        exit /b 0
    )
    :: failure
    echo #Error# The current directory path ["%WORKSPACE_ROOT%"] is too long! [Now:%CUR_DIR_LEN%, Max:%CUR_DIR_LEN_MAX%]

    ::######################
    :: Use shorter path
    ::######################

    if "%WORKSPACE_SHORT_ROOT%" equ "%WORKSPACE_ROOT%" (
        echo Please move to a shorter path.
        echo Long file names may not only cause %BASE_DIR_NAME% build failures but also lead to internal failures in UE5's Generate Solution, resulting in unusable .sln files.
        exit /b 1
    )

    :: ask to create a workspace in the shorter path
    echo Do you want to create a workspace in "%WORKSPACE_SHORT_ROOT%"?
    set /p INPUT=[y/n]:
    if /I "%INPUT%" neq "y" (
        exit /b 1
    )

    set WORKSPACE_ROOT=%WORKSPACE_SHORT_ROOT%
    call :STRLEN "%WORKSPACE_ROOT%" CUR_DIR_LEN
    if %CUR_DIR_LEN% LEQ %CUR_DIR_LEN_MAX% (
        :: ok
        exit /b 0
    )
exit /b 1

::###################################################################################
:: git
::###################################################################################

:ACTIVATE_GIT
    echo;
    echo ##### checking installed git...
    for %%A in ("%POTABLE_GIT_URL:/=" "%") do set "POTABLE_GIT_FILENAME=%%~nxA"
    set POTABLE_GIT_DL=%LIB_DIR%\%POTABLE_GIT_FILENAME%
    set POTABLE_GIT_ROOT=%LIB_DIR%\git

    :: find system git
    call :FIND_SYSTEM_EXE git --version
    if ERRORLEVEL 1 (
        :: check already installed potable git
        if not exist "%POTABLE_GIT_ROOT%\bin\git.exe" (
            echo git is not installed

            :: install potable git
            call :INSTALL_GIT
            if ERRORLEVEL 1 exit /b 1
        )

        :: append potable git path
        set "PATH=%POTABLE_GIT_ROOT%\bin;%PATH%"

        :: output git path and version
        call :WHERE_EXE git --version
        if ERRORLEVEL 1 exit /b 1
    )

    set ACTIVE_GIT=1
exit /b 0

:INSTALL_GIT
    echo ##### downloading potable git...
    curl -L %POTABLE_GIT_URL% -o "%POTABLE_GIT_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_GIT_URL% download failed
        exit /b 1
    )
    echo ##### installing potable git...
    :: Execute the self-extracting exe file
	"%POTABLE_GIT_DL%" -o "%POTABLE_GIT_ROOT%" -y
    if ERRORLEVEL 1 (
        echo %POTABLE_GIT_DL% install failed
        exit /b 1
    )

    :: delete dl file
	del "%POTABLE_GIT_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_GIT_DL% delete failed
        exit /b 1
    )

    echo git installed
exit /b 0

::###################################################################################
:: cmake
::###################################################################################

:ACTIVATE_CMAKE
    echo;
    echo ##### checking installed cmake...
    for %%A in ("%POTABLE_CMAKE_URL:/=" "%") do set "POTABLE_CMAKE_FILENAME=%%~nxA"
    set POTABLE_CMAKE_DL=%LIB_DIR%\%POTABLE_CMAKE_FILENAME%
    set POTABLE_CMAKE_ROOT=%LIB_DIR%\cmake

    :: find system cmake
    call :FIND_SYSTEM_EXE cmake --version
    if ERRORLEVEL 1 (
        :: check already installed potable cmake
        if not exist "%POTABLE_CMAKE_ROOT%\bin\cmake.exe" (
            echo cmake is not installed

            :: install potable cmake
            call :INSTALL_CMAKE
            if ERRORLEVEL 1 exit /b 1
        )
        :: append potable cmake path
        set "PATH=%POTABLE_CMAKE_ROOT%\bin;%PATH%"

        :: output cmake path and version
        call :WHERE_EXE cmake --version
        if ERRORLEVEL 1 exit /b 1
    )
    
    set ACTIVE_CMAKE=1
exit /b 0

:INSTALL_CMAKE
    echo ##### downloading potable cmake...
    curl -L %POTABLE_CMAKE_URL% -o "%POTABLE_CMAKE_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_CMAKE_URL% download failed
        exit /b 1
    )
    echo ##### installing potable cmake...
    :: unzip
    powershell -Command "Expand-Archive -Path '%POTABLE_CMAKE_DL%' -DestinationPath '%LIB_DIR%'"
    if ERRORLEVEL 1 (
        echo %POTABLE_CMAKE_DL% unzip failed
        exit /b 1
    )

    :: delete dl file
	del "%POTABLE_CMAKE_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_CMAKE_DL% delete failed
        exit /b 1
    )

    :: Extract folder name from full path
    for %%A in ("%POTABLE_CMAKE_DL:/=" "%") do set "_DL_NAME=%%~nA"
    for %%A in ("%POTABLE_CMAKE_ROOT:\=" "%") do set "_NAME=%%~nA"
    
    :: rename
    ren "%LIB_DIR%\%_DL_NAME%" "%_NAME%"
    if ERRORLEVEL 1 (
        echo %LIB_DIR%\%_DL_NAME% rename failed
        exit /b 1
    )
    echo ##### cmake installed
exit /b 0

::###################################################################################
:: chrome
::###################################################################################

:ACTIVATE_CHROME
    echo;
    echo ##### checking installed chrome...
    for %%A in ("%POTABLE_CHROME_URL:/=" "%") do set "POTABLE_CHROME_FILENAME=%%~nxA"
    set POTABLE_CHROME_DL=%LIB_DIR%\%POTABLE_CHROME_FILENAME%
    set POTABLE_CHROME_ROOT=%LIB_DIR%\chrome

    :: check already installed potable chrome
    if not exist "%POTABLE_CHROME_ROOT%\chrome.exe" (
        echo chrome is not installed

        :: install potable chrome
        call :INSTALL_CHROME
        if ERRORLEVEL 1 exit /b 1
    )

    :: check already installed potable chrome
    if not exist "%POTABLE_CHROME_ROOT%\chrome.exe" (
        echo chrome driver install failed
        exit /b 1
    )
    
    set ACTIVE_CHROME=1
exit /b 0

:INSTALL_CHROME
    echo ##### downloading potable chrome...
    curl -L %POTABLE_CHROME_URL% -o "%POTABLE_CHROME_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_CHROME_URL% download failed
        exit /b 1
    )
    echo ##### installing potable chrome...
    :: unzip
    powershell -Command "Expand-Archive -Path '%POTABLE_CHROME_DL%' -DestinationPath '%LIB_DIR%'"
    if ERRORLEVEL 1 (
        echo %POTABLE_CHROME_DL% unzip failed
        exit /b 1
    )

    :: delete dl file
	del "%POTABLE_CHROME_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_CHROME_DL% delete failed
        exit /b 1
    )

    :: Extract folder name from full path
    for %%A in ("%POTABLE_CHROME_DL:/=" "%") do set "_DL_NAME=%%~nA"
    for %%A in ("%POTABLE_CHROME_ROOT:\=" "%") do set "_NAME=%%~nA"
    
    :: rename
    ren "%LIB_DIR%\%_DL_NAME%" "%_NAME%"
    if ERRORLEVEL 1 (
        echo %LIB_DIR%\%_DL_NAME% rename failed
        exit /b 1
    )
    echo ##### chrome installed
exit /b 0

::###################################################################################
:: chrome driver
::###################################################################################

:ACTIVATE_CHROME_DRIVER
    echo;
    echo ##### checking installed chrome driver...
    for %%A in ("%POTABLE_CHROME_DRIVER_URL:/=" "%") do set "POTABLE_CHROME_DRIVER_FILENAME=%%~nxA"
    set POTABLE_CHROME_DRIVER_DL=%LIB_DIR%\%POTABLE_CHROME_DRIVER_FILENAME%
    set POTABLE_CHROME_DRIVER_ROOT=%LIB_DIR%\chrome_driver

    :: check already installed potable chrome
    if not exist "%POTABLE_CHROME_DRIVER_ROOT%\chromedriver.exe" (
        echo chrome driver is not installed

        :: install potable chrome
        call :INSTALL_CHROME_DRIVER
        if ERRORLEVEL 1 exit /b 1
    )

    :: check already installed potable chrome
    if not exist "%POTABLE_CHROME_DRIVER_ROOT%\chromedriver.exe" (
        echo chrome driver install failed
        exit /b 1
    )
    
    set ACTIVE_CHROME_DRIVER=1
exit /b 0

:INSTALL_CHROME_DRIVER
    echo ##### downloading potable chrome...
    curl -L %POTABLE_CHROME_DRIVER_URL% -o "%POTABLE_CHROME_DRIVER_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_CHROME_DRIVER_URL% download failed
        exit /b 1
    )
    echo ##### installing potable chrome...
    :: unzip
    powershell -Command "Expand-Archive -Path '%POTABLE_CHROME_DRIVER_DL%' -DestinationPath '%LIB_DIR%'"
    if ERRORLEVEL 1 (
        echo %POTABLE_CHROME_DRIVER_DL% unzip failed
        exit /b 1
    )

    :: delete dl file
	del "%POTABLE_CHROME_DRIVER_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_CHROME_DRIVER_DL% delete failed
        exit /b 1
    )

    :: Extract folder name from full path
    for %%A in ("%POTABLE_CHROME_DRIVER_DL:/=" "%") do set "_DL_NAME=%%~nA"
    for %%A in ("%POTABLE_CHROME_DRIVER_ROOT:\=" "%") do set "_NAME=%%~nA"
    
    :: rename
    ren "%LIB_DIR%\%_DL_NAME%" "%_NAME%"
    if ERRORLEVEL 1 (
        echo %LIB_DIR%\%_DL_NAME% rename failed
        exit /b 1
    )
    echo ##### chrome driver installed
exit /b 0

::###################################################################################
:: ffmpeg
::###################################################################################

:ACTIVATE_FFMPEG
    echo;
    echo ##### checking installed ffmpeg...
    for %%A in ("%POTABLE_FFMPEG_URL:/=" "%") do set "POTABLE_FFMPEG_FILENAME=%%~nxA"
    set POTABLE_FFMPEG_DL=%LIB_DIR%\%POTABLE_FFMPEG_FILENAME%
    set POTABLE_FFMPEG_ROOT=%LIB_DIR%\ffmpeg

    :: check already installed potable ffmpeg
    if not exist "%POTABLE_FFMPEG_ROOT%\bin\ffmpeg.exe" (
        echo ffmpeg is not installed

        :: install potable ffmpeg
        call :INSTALL_FFMPEG
        if ERRORLEVEL 1 exit /b 1
    )
    :: append potable ffmpeg path
    set "PATH=%POTABLE_FFMPEG_ROOT%\bin;%PATH%"

    :: output ffmpeg path and version
    call :WHERE_EXE ffmpeg.exe -version
    if ERRORLEVEL 1 exit /b 1
    
    set ACTIVE_FFMPEG=1
exit /b 0

:INSTALL_FFMPEG
    echo ##### downloading potable ffmpeg...
    curl -L %POTABLE_FFMPEG_URL% -o "%POTABLE_FFMPEG_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_FFMPEG_URL% download failed
        exit /b 1
    )
    echo ##### installing potable ffmpeg...
    :: unzip
    powershell -Command "Expand-Archive -Path '%POTABLE_FFMPEG_DL%' -DestinationPath '%LIB_DIR%'"
    if ERRORLEVEL 1 (
        echo %POTABLE_FFMPEG_DL% unzip failed
        exit /b 1
    )

    :: delete dl file
	del "%POTABLE_FFMPEG_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_FFMPEG_DL% delete failed
        exit /b 1
    )

    :: Extract folder name from full path
    for %%A in ("%POTABLE_FFMPEG_DL:/=" "%") do set "_DL_NAME=%%~nA"
    for %%A in ("%POTABLE_FFMPEG_ROOT:\=" "%") do set "_NAME=%%~nA"
    
    :: rename
    ren "%LIB_DIR%\%_DL_NAME%" "%_NAME%"
    if ERRORLEVEL 1 (
        echo %LIB_DIR%\%_DL_NAME% rename failed
        exit /b 1
    )
    echo ##### ffmpeg installed
exit /b 0

::###################################################################################
:: nodejs
::###################################################################################

:ACTIVATE_NODEJS
    echo;
    echo ##### checking installed nodejs...
    for %%A in ("%POTABLE_NODEJS_URL:/=" "%") do set "POTABLE_NODEJS_FILENAME=%%~nxA"
    set POTABLE_NODEJS_DL=%LIB_DIR%\%POTABLE_NODEJS_FILENAME%
    set POTABLE_NODEJS_ROOT=%LIB_DIR%\nodejs

    :: check already installed potable nodejs
    call :FIND_SYSTEM_EXE npm --version
    if ERRORLEVEL 1 (
	    if not exist "%POTABLE_NODEJS_ROOT%\npm" (
	        echo nodejs is not installed

	        :: install potable nodejs
	        call :INSTALL_NODEJS
	        if ERRORLEVEL 1 exit /b 1
	    )
	    :: append potable nodejs path
	    set "PATH=%POTABLE_NODEJS_ROOT%;%PATH%"

	    :: output nodejs path and version
	    call :WHERE_EXE npm --version
	    if ERRORLEVEL 1 exit /b 1
    )
    
    set ACTIVE_NODEJS=1
exit /b 0

:INSTALL_NODEJS
    echo ##### downloading potable nodejs...
    curl -L %POTABLE_NODEJS_URL% -o "%POTABLE_NODEJS_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_NODEJS_URL% download failed
        exit /b 1
    )
    echo ##### installing potable nodejs...
    :: unzip
    powershell -Command "Expand-Archive -Path '%POTABLE_NODEJS_DL%' -DestinationPath '%LIB_DIR%'"
    if ERRORLEVEL 1 (
        echo %POTABLE_NODEJS_DL% unzip failed
        exit /b 1
    )

    :: delete dl file
	del "%POTABLE_NODEJS_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_NODEJS_DL% delete failed
        exit /b 1
    )

    :: Extract folder name from full path
    for %%A in ("%POTABLE_NODEJS_DL:/=" "%") do set "_DL_NAME=%%~nA"
    for %%A in ("%POTABLE_NODEJS_ROOT:\=" "%") do set "_NAME=%%~nA"
    
    :: rename
    ren "%LIB_DIR%\%_DL_NAME%" "%_NAME%"
    if ERRORLEVEL 1 (
        echo %LIB_DIR%\%_DL_NAME% rename failed
        exit /b 1
    )
    echo ##### nodejs installed
exit /b 0

::###################################################################################
:: go
::###################################################################################

:ACTIVATE_GO
    echo;
    echo ##### checking installed go...
    for %%A in ("%POTABLE_GO_URL:/=" "%") do set "POTABLE_GO_FILENAME=%%~nxA"
    set POTABLE_GO_DL=%LIB_DIR%\%POTABLE_GO_FILENAME%
    set POTABLE_GO_ROOT=%LIB_DIR%\go

    :: check already installed potable go
    call :FIND_SYSTEM_EXE go version
    if ERRORLEVEL 1 (
	    if not exist "%POTABLE_GO_ROOT%\bin\go.exe" (
	        echo go is not installed

	        :: install potable go
	        call :INSTALL_GO
	        if ERRORLEVEL 1 exit /b 1
	    )
	    :: append potable go path
	    set "PATH=%POTABLE_GO_ROOT%\bin;%PATH%"

	    :: output nodejs path and version
	    call :WHERE_EXE go version
	    if ERRORLEVEL 1 exit /b 1
    )
    
    set ACTIVE_GO=1
exit /b 0

:INSTALL_GO
    echo ##### downloading potable go...
    curl -L %POTABLE_GO_URL% -o "%POTABLE_GO_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_GO_URL% download failed
        exit /b 1
    )
    echo ##### installing potable go...
    :: unzip
    powershell -Command "Expand-Archive -Path '%POTABLE_GO_DL%' -DestinationPath '%LIB_DIR%'"
    if ERRORLEVEL 1 (
        echo %POTABLE_GO_DL% unzip failed
        exit /b 1
    )

    :: delete dl file
	del "%POTABLE_GO_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_GO_DL% delete failed
        exit /b 1
    )
    
    echo ##### go installed
exit /b 0

::###################################################################################
:: python
::###################################################################################

:ACTIVATE_PYTHON
    echo;
    echo ##### checking installed python...
    for %%A in ("%POTABLE_PYTHON_URL:/=" "%") do set "POTABLE_PYTHON_FILENAME=%%~nxA"
    set POTABLE_PYTHON_DL=%LIB_DIR%\%POTABLE_PYTHON_FILENAME%
    set POTABLE_PYTHON_ROOT=%LIB_DIR%\python
    set POTABLE_PYTHON_CMD=%POTABLE_PYTHON_ROOT%\python
    set VENV_DIR=%WORKSPACE_ROOT%\%PYTHON_VENV_DIR_NAME%

    :: find system python
    call :FIND_SYSTEM_EXE python --version
    if ERRORLEVEL 1 (
        :: check already installed potable python
        if not exist "%POTABLE_PYTHON_ROOT%\python.exe" (
            echo ##### python is not installed

            :: install potable python
            call :INSTALL_PYTHON
            if ERRORLEVEL 1 exit /b 1

            set SETUPED_PYTHON=1
        )

        :: append potable python path
        set "PATH=%POTABLE_PYTHON_ROOT%;%PATH%"
        
        :: output python path and version
        call :WHERE_EXE python --version
        if ERRORLEVEL 1 exit /b 1
    )
    
    :: activate venv
    if "%ENABLE_PYTHON_VENV%" equ "1" (
        call :ACTIVATE_PYTHON_VENV
        if ERRORLEVEL 1 exit /b 1
    )
    
    :: install required python module if setuped python or venv
    if "%SETUPED_PYTHON%%SETUPED_VENV%" neq "" (
        call :INSTALL_REQUIRED_PYTHON_MODULE
        if ERRORLEVEL 1 exit /b 1
    )
    
    set ACTIVE_PYTHON=1
exit /b 0

:INSTALL_PYTHON
    echo ##### downloading potable ython...
    curl -L %POTABLE_PYTHON_URL% -o "%POTABLE_PYTHON_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_PYTHON_URL% download failed
        exit /b 1
    )
    echo ##### installing potable python...
    :: unzip
    powershell -Command "Expand-Archive -Path '%POTABLE_PYTHON_DL%' -DestinationPath '%POTABLE_PYTHON_ROOT%'"
    if ERRORLEVEL 1 (
        echo %POTABLE_PYTHON_DL% unzip failed
        exit /b 1
    )

    :: delete dl file
	del "%POTABLE_PYTHON_DL%"
    if ERRORLEVEL 1 (
        echo %POTABLE_PYTHON_DL% delete failed
        exit /b 1
    )
    
    echo ## enabling 'site' module...
    :: find pythonXXX._pth. and replace '#import site' to 'import site'
    for /r "%POTABLE_PYTHON_ROOT%" %%f in (python*._pth) do (
    	powershell "&{(Get-Content '%%f') -creplace '#import site', 'import site' | Set-Content '%%f' }"
        if ERRORLEVEL 1 (
            echo '%%f' replace failed
            exit /b 1
        )
    )
    
    :: add current directory to sys.path
    echo import sys; sys.path.append('') >> "%POTABLE_PYTHON_ROOT%\current.pth"

    echo ## downloading pip...
    curl -sSL "%POTABLE_PYTHON_PIP_URL%" -o "%POTABLE_PYTHON_ROOT%\get-pip.py"
    if ERRORLEVEL 1 (
        echo %POTABLE_PYTHON_PIP_URL% download failed
        exit /b 1
    )
    
    echo ## installing pip...
	"%POTABLE_PYTHON_CMD%" "%POTABLE_PYTHON_ROOT%\get-pip.py" --no-warn-script-location
    if ERRORLEVEL 1 (
        echo pip install failed
        exit /b 1
    )
    
    echo ## installing virtualenv...
    "%POTABLE_PYTHON_CMD%" -m pip install virtualenv --no-warn-script-location
    if ERRORLEVEL 1 (
        echo virtualenv install failed
        exit /b 1
    )

    echo ##### python installed
exit /b 0

:ACTIVATE_PYTHON_VENV
    :: check venv directory and activate venv
    if exist "%VENV_DIR%\" (
        call "%VENV_DIR%\Scripts\activate.bat"
        if ERRORLEVEL 1 exit /b 1
        exit /b 0
    )

    echo ##### venv directory not found.
    echo ## creating python venv...

    :: check venv module (python standard module)
    "%POTABLE_PYTHON_CMD%" -c "import venv" >nul 2>&1
    if ERRORLEVEL 1 (
        :: use virtualenv (installed virtualenv module)
        "%POTABLE_PYTHON_CMD%" -m virtualenv "%VENV_DIR%"
        if ERRORLEVEL 1 (
            echo virtualenv create failed
            exit /b 1
        )
    ) else (
        :: use venv (python standard module)
        "%POTABLE_PYTHON_CMD%" -m venv "%VENV_DIR%"
        if ERRORLEVEL 1 (
            echo venv create failed
            exit /b 1
        )
    )

    set SETUPED_VENV=1

    :: activate venv
    call "%VENV_DIR%\Scripts\activate.bat"
    if ERRORLEVEL 1 exit /b 1
exit /b 0

:INSTALL_REQUIRED_PYTHON_MODULE
    echo ## installing required modules...
    if exist "%CUR_DIR%requirements.txt" (
        python -m pip install -r requirements.txt
        if ERRORLEVEL 1 exit /b 1
    )
    if "%POTABLE_PYTHON_REQUIREMENT_MODULES%" neq "" (
        python -m pip install %POTABLE_PYTHON_REQUIREMENT_MODULES%
        if ERRORLEVEL 1 exit /b 1
    )
exit /b 0


::###################################################################################
:: CUDA Toolkit
::###################################################################################

:ACTIVATE_CUDA
    echo;
    echo ##### checking installed CUDA Toolkit...
    for %%A in ("%CUDA_URL:/=" "%") do set "CUDA_FILENAME=%%~nxA"
    set CUDA_DL=%LIB_DIR%\%CUDA_FILENAME%

    :: check installed CUDA Toolkit
    if exist "%CUDA_PATH%\bin\nvcc.exe" (
        echo CUDA Toolkit is installed.
        set ACTIVE_CUDA=1
        exit /b 0
    )
    echo CUDA Toolkit is not installed.
    echo;
    echo Do you want to install CUDA Toolkit?
    echo ^(CUDA will not be built if not installed CUDA Toolkit.^)
    set /p INPUT=[y/n]:
    if /I "%INPUT%" neq "y" (
        echo CUDA Toolkit was not installed.
        exit /b 0
    )
    
    :: install cuda Toolkit
    call :INSTALL_CUDA
    if ERRORLEVEL 1 exit /b 1
    
    set ACTIVE_CUDA=1
exit /b 0

:INSTALL_CUDA
    echo ##### downloading CUDA Toolkit...
    curl -L %CUDA_URL% -o "%CUDA_DL%"
    if ERRORLEVEL 1 (
        echo %CUDA_URL% download failed
        exit /b 1
    )
    echo ##### installing CUDA Toolkit...
    :: silent install.
    :: echo Please wait until the installation is complete. This may take some time.
	:: "%CUDA_DL%" -s
    start /wait "" "%CUDA_DL%"
    if ERRORLEVEL 1 (
        echo %CUDA_DL% install failed
        exit /b 1
    )

    :: delete dl file
	del "%CUDA_DL%"
    if ERRORLEVEL 1 (
        echo %CUDA_DL% delete failed
        exit /b 1
    )

    :: Update the "CUDA_*" environment variable without restarting the command prompt
    call :UPDATE_SYSTEM_ENVS CUDA_

    :: check installed cuda Toolkit
    if not exist "%CUDA_PATH%\bin\nvcc.exe" (
        echo CUDA Toolkit install failed
        exit /b 1
    )

    :: Update PATH without restarting the command prompt
    set "PATH=%CUDA_PATH%\libnvvp;%PATH%"
    set "PATH=%CUDA_PATH%\bin;%PATH%"
    
    echo CUDA Toolkit installed
exit /b 0

::###################################################################################
:: Vulkan SDK
::###################################################################################

:ACTIVATE_VULKAN
    echo;
    echo ##### checking installed Vulkan SDK...
    for %%A in ("%VULKAN_URL:/=" "%") do set "VULKAN_FILENAME=%%~nxA"
    set VULKAN_DL=%LIB_DIR%\%VULKAN_FILENAME%

    :: check installed Vulkan SDK
    if exist "%VULKAN_SDK%\Bin\glslc.exe" (
        echo Vulkan SDK is installed.
        set ACTIVE_VULKAN=1
        exit /b 0
    )

    echo Vulkan SDK is not installed.
    echo;
    echo Do you want to install Vulkan SDK?
    echo ^(Vulkan will not be built if not installed Vulkan SDK.^)
    echo ^(If installing, Only the Core installation configuration is required. The default settings are fine.^)
    set /p INPUT=[y/n]:
    if /I "%INPUT%" neq "y" (
        echo Vulkan SDK was not installed.
        exit /b 0
    )
    
    :: install Vulkan SDK
    call :INSTALL_VULKAN
    if ERRORLEVEL 1 exit /b 1
    
    set ACTIVE_VULKAN=1
exit /b 0

:INSTALL_VULKAN
    echo ##### downloading Vulkan SDK...
    curl -L %VULKAN_URL% -o "%VULKAN_DL%"
    if ERRORLEVEL 1 (
        echo %VULKAN_URL% download failed
        exit /b 1
    )
    echo ##### installing Vulkan SDK...
    :: silent install.
    :: echo Please wait until the installation is complete. This may take some time.
	:: "%VULKAN_DL%" -s
    start /wait "" "%VULKAN_DL%"
    if ERRORLEVEL 1 (
        echo %VULKAN_DL% install failed
        exit /b 1
    )

    :: delete dl file
	del "%VULKAN_DL%"
    if ERRORLEVEL 1 (
        echo %VULKAN_DL% delete failed
        exit /b 1
    )

    :: Update the "VK_SDK_PATH" and "VULKAN_SDK" environment variable without restarting the command prompt
    call :UPDATE_SYSTEM_ENV VK_SDK_PATH
    call :UPDATE_SYSTEM_ENV VULKAN_SDK

    :: check installed Vulkan SDK
    if not exist "%VULKAN_SDK%\Bin\glslc.exe" (
        echo Vulkan SDK install failed
        exit /b 1
    )

    :: Update PATH without restarting the command prompt
    set "PATH=%VULKAN_SDK%\Bin;%PATH%"
    
    echo Vulkan SDK installed
exit /b 0

::###################################################################################
:: checkout llama-balancer
::###################################################################################

:CHECKOUT_LLAMA_BALANCER
    echo;
    echo ##### checking checkout llama-balancer...
    set LLAMA_BALANCER_NAME=llama-balancer
    set LLAMA_BALANCER_REPO=%CUR_DIR%
    set LLAMA_BALANCER_CHECK_FILE=%LLAMA_BALANCER_REPO%\.git
    set LLAMA_BALANCER_URL=https://github.com/issixx/llama-balancer.git
    
    :: backslash to slash and remove last slash
    set "LLAMA_BALANCER_REPO=%LLAMA_BALANCER_REPO:\=/%"
    if "%LLAMA_BALANCER_REPO:~-1%"=="/" set "LLAMA_BALANCER_REPO=%LLAMA_BALANCER_REPO:~0,-1%"
    
	if not exist "%LLAMA_BALANCER_CHECK_FILE%" (
	    echo # checking out %LLAMA_BALANCER_NAME%...
        
        git -C "%LLAMA_BALANCER_REPO%" init -b main
		if ERRORLEVEL 1 (
			echo failed to init "%LLAMA_BALANCER_NAME%"
			exit /b 1
		)

        git -C "%LLAMA_BALANCER_REPO%" remote add origin %LLAMA_BALANCER_URL%
		if ERRORLEVEL 1 (
			echo failed to remote "%LLAMA_BALANCER_NAME%"
			exit /b 1
		)
        git -C "%LLAMA_BALANCER_REPO%" fetch
		if ERRORLEVEL 1 (
			echo failed to fetch "%LLAMA_BALANCER_NAME%"
			exit /b 1
		)
        git -C "%LLAMA_BALANCER_REPO%" checkout -f -t origin/main
		if ERRORLEVEL 1 (
			echo failed to checkout "%LLAMA_BALANCER_NAME%"
			exit /b 1
		)
	    if exist "%CUR_DIR%requirements.txt" (
	    	echo # installing required modules...
	        python -m pip install -r requirements.txt
	        if ERRORLEVEL 1 exit /b 1
	    )
    
        if exist "%LLAMA_BALANCER_CHECK_FILE%" (
            echo # checkout successfully %LLAMA_BALANCER_NAME%...
        )
	)
exit /b 0
