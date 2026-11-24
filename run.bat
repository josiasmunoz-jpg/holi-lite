@echo off
rem Ejecuta Holi desde el codigo fuente. La primera vez crea el entorno e instala dependencias.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Preparando entorno, solo la primera vez...
    python -m venv .venv || goto :nopython
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:nopython
echo No encontre Python. Instala Python 3.10 o superior (Microsoft Store o python.org).
pause
exit /b 1

:error
echo Fallo la instalacion de dependencias.
pause
exit /b 1
