@echo off
REM Instalar publicador automático aapanel - Windows (Task Scheduler)

set "SCRIPT_DIR=%~dp0"
set "BASE_DIR=%SCRIPT_DIR%\..\.."
set "PUBLISHER_SCRIPT=%BASE_DIR%\skills\deploy-aapanel\references\publicar-aapanel.py"
set "TASK_NAME=ProspectorPublicador"

echo 🔧 Instalando publicador automático aapanel (Windows Task Scheduler)...

REM Verificar script
if not exist "%PUBLISHER_SCRIPT%" (
    echo ❌ Script não encontrado: %PUBLISHER_SCRIPT%
    echo    Rode /setup primeiro para copiar os arquivos.
    pause
    exit /b 1
)

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python não encontrado. Instale em https://python.org
    echo    Durante a instalação, marque "Add Python to PATH"
    pause
    exit /b 1
)

REM Criar task no Agendador (roda a cada 1 minuto)
schtasks /create /tn "%TASK_NAME%" /tr "python \"%PUBLISHER_SCRIPT%\"" /sc minute /mo 1 /f /rl highest /rl highest /it 2>nul

if errorlevel 1 (
    echo ⚠️  Pode precisar rodar como Administrador
    echo    Tentando com privilégios elevados...
    powershell -Command "Start-Process schtasks -ArgumentList '/create /tn \"%TASK_NAME%\" /tr \"python \"%PUBLISHER_SCRIPT%\"\" /sc minute /mo 1 /f /rl highest /it' -Verb RunAs"
)

echo ✅ Task agendada criada: %TASK_NAME%
echo    Roda a cada 1 minuto verificando fila-publicacao.txt
echo.
echo    Ver logs: %BASE_DIR%\publicador-log.txt
echo    Ver task: Abra "Task Scheduler" → Task Scheduler Library → %TASK_NAME%
echo    Desinstalar: schtasks /delete /tn "%TASK_NAME%" /f
pause