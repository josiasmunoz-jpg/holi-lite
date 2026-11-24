@echo off
rem Arma Holi Lite, crea el instalador (entregar\HoliLite-Setup-<version>.exe) y lo instala en este PC.
rem El instalador es lo que le pasas a otra persona: un solo archivo, sin Python ni permisos de administrador.
rem Tus planetas y ajustes se mantienen.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || goto :nopython
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller pillow || goto :error
if not exist "assets\blob.ico" ".venv\Scripts\python.exe" tools\make_icon.py

echo Cerrando Holi si esta abierto...
".venv\Scripts\python.exe" main.py --quit
timeout /t 2 /nobreak >nul

echo Armando la aplicacion...
rem el .spec que genera PyInstaller queda en build_app (no ensucia la carpeta del proyecto)
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --name HoliLite --icon "%~dp0assets\blob.ico" ^
    --distpath app_build --workpath build_app --specpath build_app ^
    "%~dp0main.py" || goto :error

echo Armando el instalador...
".venv\Scripts\python.exe" tools\make_setup.py || goto :error

echo Instalando...
for %%f in ("entregar\HoliLite-Setup-*.exe") do start "" /wait "%%f" --silencioso
echo.
echo Listo. El instalador para compartir quedo en la carpeta "entregar".
timeout /t 4 >nul
exit /b 0

:nopython
echo No encontre Python. Instala Python 3.10 o superior (Microsoft Store o python.org).
pause
exit /b 1

:error
echo Algo fallo. Revisa los mensajes de arriba.
pause
exit /b 1
