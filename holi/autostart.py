"""Inicio automatico con Windows (clave Run del usuario, no requiere permisos de administrador)."""
import os
import sys

from . import config as C

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _command():
    if getattr(sys, "frozen", False):                 # .exe compilado
        return '"{}"'.format(sys.executable)
    main = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    exe = sys.executable
    alias = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "pythonw.exe")
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    elif os.path.exists(alias):
        exe = alias
    return '"{}" "{}"'.format(exe, main)


def supported():
    return sys.platform.startswith("win")


def is_enabled():
    if not supported():
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, C.APP_NAME)
            return True
    except OSError:
        return False


def set_enabled(on):
    if not supported():
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, C.APP_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(k, C.APP_NAME)
            except OSError:
                pass
