"""Arma el instalador de un solo archivo: entregar\\HoliLite-Setup-<version>.exe.
Necesita la aplicacion ya armada en app_build\\HoliLite (lo hace instalar.bat antes de llamar a esto)."""
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from holi import __version__  # noqa: E402

APP = os.path.join(ROOT, "app_build", "HoliLite")
WORK = os.path.join(ROOT, "build_setup")
OUT = os.path.join(ROOT, "entregar")


def main():
    if not os.path.exists(os.path.join(APP, "HoliLite.exe")):
        sys.exit("Falta app_build\\HoliLite: corre instalar.bat")
    os.makedirs(WORK, exist_ok=True)
    payload = os.path.join(WORK, "payload.zip")
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for folder, _dirs, files in os.walk(APP):
            for f in files:
                full = os.path.join(folder, f)
                z.write(full, "HoliLite/" + os.path.relpath(full, APP).replace(os.sep, "/"))
        z.write(os.path.join(ROOT, "assets", "blob.ico"), "blob.ico")
        z.writestr("version.txt", __version__)
    name = "HoliLite-Setup-" + __version__
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        "--name", name, "--icon", os.path.join(ROOT, "assets", "blob.ico"),
        "--add-data", payload + os.pathsep + ".",
        "--distpath", OUT, "--workpath", WORK, "--specpath", WORK,
        os.path.join(ROOT, "tools", "setup.py"),
    ])
    # deja solo la version nueva en entregar
    for f in os.listdir(OUT):
        if f.startswith("HoliLite-Setup-") and f != name + ".exe":
            os.remove(os.path.join(OUT, f))
    print(os.path.join(OUT, name + ".exe"))


if __name__ == "__main__":
    main()
