@echo off
REM Build script for Wii Mouse Driver executable

echo ========================================
echo  Wii Mouse Driver - Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller nao encontrado. Instalando...
    pip install pyinstaller
    if errorlevel 1 (
        echo Erro ao instalar PyInstaller!
        pause
        exit /b 1
    )
)

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "Wii Mouse Driver.spec" del "Wii Mouse Driver.spec"

echo.
echo Instalando dependencias (requirements.txt)...
pip install -r requirements.txt
if errorlevel 1 (
    echo Erro ao instalar dependencias!
    pause
    exit /b 1
)

echo.
echo Gerando executavel...
echo.

REM Build executable
pyinstaller --name="Wii Mouse Driver" ^
    --onefile ^
    --windowed ^
    --icon=NONE ^
    --add-data "config.ini;." ^
    --hidden-import=hid ^
    --hidden-import=pyautogui ^
    --hidden-import=pynput ^
    --hidden-import=pynput.keyboard ^
    --hidden-import=pynput.mouse ^
    --hidden-import=PIL._tkinter_finder ^
    --collect-all=pyautogui ^
    --collect-all=pynput ^
    --collect-submodules=tkinter ^
    --copy-metadata=pyautogui ^
    --copy-metadata=pynput ^
    main.py

if errorlevel 1 (
    echo.
    echo Erro ao gerar executavel!
    pause
    exit /b 1
)

echo.
echo ========================================
echo  Build concluido com sucesso!
echo ========================================
echo.
echo O executavel esta em: dist\Wii Mouse Driver.exe
echo.

REM Copy config file to dist
if exist config.ini (
    copy /y config.ini dist\config.ini >nul
    echo Arquivo config.ini copiado para dist\
)

echo.
echo Deseja abrir a pasta dist? (S/N)
set /p OPEN_DIST=

if /i "%OPEN_DIST%"=="S" (
    explorer dist
)

pause
