"""Instalador de Holi Lite (HoliLite-Setup-x.y.z.exe). Solo usa la biblioteca estandar de Python,
asi queda chico; la aplicacion viaja adentro en payload.zip (lo arma tools/make_setup.py).

Instala para el usuario actual, sin permisos de administrador:
  - programa en %LOCALAPPDATA%\\Programs\\Holi Lite
  - accesos directos en el menu Inicio y en el escritorio
  - aparece en Configuracion > Aplicaciones (desinstala con "HoliLite.exe --uninstall")
Si ya estaba instalado, lo reemplaza y los planetas y ajustes se mantienen.
La primera vez pregunta como se va a llamar la mascota (despues se cambia en Opciones > Nombre).
Con --silencioso no pregunta nada (lo usa instalar.bat).
"""
import ctypes
import os
import random
import shutil
import subprocess
import sys
import time
import winreg
import zipfile

TITLE = "Holi Lite"
UNKEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HoliLite"
SETTINGS = r"Software\Holi\Holi Lite"          # donde guarda sus ajustes la aplicacion (QSettings)
NO_WINDOW = 0x08000000
YES = 6


def message(text, flags=0x40):
    return ctypes.windll.user32.MessageBoxW(None, text, TITLE, flags)


def clean_env():
    """Entorno para abrir Holi desde el instalador. Los dos estan hechos con PyInstaller y, si Holi
    hereda las variables del instalador, falla con "Failed to start embedded python interpreter"."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("_PYI", "_MEI"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def run_hidden(args, **kw):
    return subprocess.run(args, creationflags=NO_WINDOW, capture_output=True, **kw)


def saved_name():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SETTINGS) as k:
            return str(winreg.QueryValueEx(k, "name")[0]).strip()
    except OSError:
        return ""


def ask_name():
    """Ventanita de Windows para escribir el nombre (sin agregar nada al instalador)."""
    ps = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; Add-Type -AssemblyName Microsoft.VisualBasic; "
          "[Microsoft.VisualBasic.Interaction]::InputBox('Ponle nombre a tu mascota (lo puedes cambiar después en Opciones).', "
          "'Holi Lite', 'Holi')")
    try:
        out = run_hidden(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=600)
        name = " ".join(out.stdout.decode("utf-8", "ignore").split())[:20]
    except (OSError, subprocess.TimeoutExpired):
        name = ""
    return name or "Holi"


def install(quiet):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    payload = zipfile.ZipFile(os.path.join(base, "payload.zip"))
    version = payload.read("version.txt").decode().strip()
    if not quiet:
        ask = ("¿Instalar Holi Lite %s?\n\nSe instala solo para tu usuario y no pide permisos de administrador. "
               "Si ya lo tenías, se actualiza y tus planetas y ajustes se mantienen." % version)
        if message(ask, 0x04 | 0x20) != YES:
            return

    if not quiet and not saved_name():
        name = ask_name()
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, SETTINGS) as k:
            winreg.SetValueEx(k, "name", 0, winreg.REG_SZ, name)

    appdir = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Holi Lite")
    exe = os.path.join(appdir, "HoliLite.exe")

    # cierra el que esta abierto (guarda sus planetas al cerrarse)
    if os.path.exists(exe):
        try:
            run_hidden([exe, "--quit"], timeout=15, env=clean_env())
        except (OSError, subprocess.TimeoutExpired):
            pass
        time.sleep(1.5)
    run_hidden(["taskkill", "/im", "HoliLite.exe", "/f"])

    # reemplaza la carpeta del programa
    for _ in range(10):
        shutil.rmtree(appdir, ignore_errors=True)
        if not os.path.exists(appdir):
            break
        time.sleep(0.5)
    os.makedirs(appdir, exist_ok=True)
    size = 0
    for info in payload.infolist():
        if not info.filename.startswith("HoliLite/") or info.is_dir():
            continue
        dest = os.path.join(appdir, *info.filename[len("HoliLite/"):].split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with payload.open(info) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
        size += info.file_size
    # icono con nombre nuevo en cada instalacion: Windows guarda los iconos por ruta y si no, muestra el viejo
    icon = os.path.join(appdir, "holi-%d.ico" % random.randint(10 ** 7, 10 ** 8))
    with open(icon, "wb") as out:
        out.write(payload.read("blob.ico"))

    # accesos directos (el escritorio puede estar en OneDrive: PowerShell sabe donde esta)
    ps = ("$s = New-Object -ComObject WScript.Shell; "
          "foreach ($d in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) { "
          "$l = $s.CreateShortcut((Join-Path $d 'Holi Lite.lnk')); $l.TargetPath = '%s'; $l.WorkingDirectory = '%s'; "
          "$l.IconLocation = '%s,0'; $l.Description = 'Holi Lite, tu mascota de escritorio'; $l.Save() }"
          % (exe, appdir, icon))
    run_hidden(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])
    run_hidden(["ie4uinit.exe", "-show"])

    # Configuracion > Aplicaciones
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNKEY) as k:
        for name, value in (("DisplayName", TITLE), ("DisplayVersion", version), ("Publisher", "Holi"),
                            ("DisplayIcon", icon), ("InstallLocation", appdir),
                            ("UninstallString", '"%s" --uninstall' % exe)):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        for name, value in (("NoModify", 1), ("NoRepair", 1), ("EstimatedSize", size // 1024)):
            winreg.SetValueEx(k, name, 0, winreg.REG_DWORD, value)

    subprocess.Popen([exe], cwd=appdir, close_fds=True, env=clean_env())


if __name__ == "__main__":
    try:
        install("--silencioso" in sys.argv)
    except Exception as exc:
        message("No se pudo instalar Holi Lite:\n\n%s" % exc, 0x10)
        sys.exit(1)
