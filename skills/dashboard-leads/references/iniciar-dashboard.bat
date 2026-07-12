@echo off
REM Iniciar Dashboard Prospector - Windows

set BASE_DIR=%~dp0..\..\..
set SERVER_SCRIPT=%BASE_DIR%\skills\dashboard-leads\references\dashboard-server.py
set DB_FILE=%BASE_DIR%\prospector.db

echo 🚀 Iniciando Prospector Dashboard...

REM Verificar Python
where python >nul 2>nul
if errorlevel 1 (
    echo ❌ Python não encontrado no PATH.
    echo    Instale em: https://python.org/downloads
    echo    (Marque "Add Python to PATH" na instalação)
    pause
    exit /b 1
)

REM Verificar script do servidor
if not exist "%SERVER_SCRIPT%" (
    echo ❌ Script do servidor não encontrado: %SERVER_SCRIPT%
    echo    Rode /setup primeiro para copiar os arquivos.
    pause
    exit /b 1
)

REM Inicializar banco se não existe
if not exist "%DB_FILE%" (
    echo 📦 Criando banco de dados...
    python -c "
import sqlite3
conn = sqlite3.connect(r'%DB_FILE%')
conn.executescript('''
CREATE TABLE IF NOT EXISTS leads(
  slug TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT, nota REAL, avaliacoes INTEGER,
  email TEXT, telefone TEXT, whatsapp TEXT, siteAntigo TEXT, motivo TEXT,
  status TEXT DEFAULT 'novo', urlNova TEXT, dataProposta TEXT, valor REAL, obs TEXT,
  contratoStatus TEXT DEFAULT 'pendente', contratoEm TEXT, manutencao REAL, pago INTEGER DEFAULT 0,
  docCliente TEXT, endCliente TEXT,
  atualizado TEXT DEFAULT (datetime('now','localtime')));
''')
conn.commit()
print('✅ Banco criado:', r'%DB_FILE%')
"
)

REM Gerar dashboard.html inicial se não existe
set DASHBOARD_HTML=%BASE_DIR%\dashboard.html
if not exist "%DASHBOARD_HTML%" (
    echo 📄 Gerando dashboard.html inicial...
    python "%SERVER_SCRIPT%" --generate-only
)

echo.
echo ✅ Dashboard disponível em: http://localhost:8765
echo    Pressione Ctrl+C para parar
echo.

cd /d "%BASE_DIR%"
python "%SERVER_SCRIPT%"