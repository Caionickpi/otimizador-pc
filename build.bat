@echo off
REM ============================================================
REM  Otimizador PC - gera o executavel (.exe) para Windows.
REM  Basta dar um DUPLO-CLIQUE neste arquivo dentro do Windows.
REM  (Requer Python 3.11+ instalado e no PATH.)
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo ============================================================
echo   Otimizador PC - gerando o executavel (.exe)
echo ============================================================
echo.

REM --- 1) Confirma que o Python esta instalado ---------------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado no PATH.
    echo.
    echo   Instale o Python 3.11 ou superior em:
    echo     https://www.python.org/downloads/
    echo   Durante a instalacao, marque "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

REM --- 2) Cria o ambiente virtual (se ainda nao existir) -----
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Criando ambiente virtual .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual .venv
        pause
        exit /b 1
    )
) else (
    echo [1/4] Ambiente virtual .venv ja existe - reaproveitando.
)

REM --- 3) Instala as dependencias ----------------------------
echo [2/4] Instalando dependencias (rich, psutil, pywin32, pyinstaller...) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias.
    pause
    exit /b 1
)

REM --- 4) Gera o .exe usando a receita OtimizadorPC.spec -----
echo [3/4] Compilando o executavel (pode levar alguns minutos) ...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean OtimizadorPC.spec
if errorlevel 1 (
    echo [ERRO] Falha ao gerar o executavel.
    pause
    exit /b 1
)

echo [4/4] Concluido com sucesso!
echo.
echo ============================================================
echo   PRONTO! O executavel foi gerado em:
echo.
echo       dist\OtimizadorPC.exe
echo.
echo   - Da um duplo-clique para abrir.
echo   - Para aplicar ajustes, rode como administrador
echo     (clique com o botao direito - "Executar como administrador").
echo ============================================================
echo.
pause
endlocal
