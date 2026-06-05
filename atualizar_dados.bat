@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ==========================================
echo  Atualizando dados do dashboard JR
echo ==========================================
echo.

git --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Git nao encontrado neste computador.
    echo Instale o Git ou abra esta pasta em um ambiente com Git configurado.
    pause
    exit /b 1
)

git status --short
echo.

git add -- "*.xls" "*.xlsx"

git diff --cached --quiet
if not errorlevel 1 (
    echo Nenhuma alteracao de planilha para enviar.
    echo.
    pause
    exit /b 0
)

set "MSG=Atualiza dados da planilha %date% %time%"
git commit -m "%MSG%"
if errorlevel 1 (
    echo.
    echo ERRO: Nao foi possivel criar o commit.
    pause
    exit /b 1
)

git push origin main
if errorlevel 1 (
    echo.
    echo ERRO: Nao foi possivel enviar para o GitHub.
    echo Verifique sua internet ou login do GitHub.
    pause
    exit /b 1
)

echo.
echo Dados atualizados no GitHub com sucesso.
echo Se o dashboard estiver aberto localmente, atualize a pagina no navegador.
echo.
pause
