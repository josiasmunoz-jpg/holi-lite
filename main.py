"""Holi Lite: solo la mascota de escritorio."""
import sys
import time

from PySide6.QtGui import QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from holi import autostart, guard
from holi import config as C


def already_running(replace=False):
    """Si ya esta abierto: lo trae (o, si replace, le pide cerrarse para tomar su lugar)."""
    sock = QLocalSocket()
    sock.connectToServer(C.SINGLE_INSTANCE_KEY)
    if not sock.waitForConnected(300):
        return False
    sock.write(b"replace" if replace else b"show")
    sock.waitForBytesWritten(300)
    sock.waitForDisconnected(1500)
    if replace:
        time.sleep(0.4)
        return False
    return True


def main():
    guard.install()                          # ningun error escapado cierra a Holi: queda en errores.txt
    app = QApplication(sys.argv)
    app.setApplicationName(C.APP_NAME)
    app.setOrganizationName(C.ORG_NAME)
    app.setQuitOnLastWindowClosed(False)

    if "--quit" in sys.argv:                 # lo usan instalar.bat y el instalador para cerrar el que esta abierto
        already_running(replace=True)
        return 0
    if "--uninstall" in sys.argv:            # Configuracion > Aplicaciones > Desinstalar
        return uninstall()

    if already_running():                    # ya estaba abierto: lo trae al centro en vez de abrir otro
        return 0
    frozen = getattr(sys, "frozen", False)

    server = QLocalServer()
    QLocalServer.removeServer(C.SINGLE_INSTANCE_KEY)
    server.listen(C.SINGLE_INSTANCE_KEY)

    # abrir con Windows: solo si lo activaste en Opciones (no se activa solo). Si esta activo,
    # se vuelve a apuntar al .exe actual por si se instalo en otra carpeta.
    if frozen and autostart.is_enabled():
        autostart.set_enabled(True)

    try:
        from holi.app import Controller
        from holi.renderer import icon_pixmap
        app.setWindowIcon(QIcon(icon_pixmap(64)))
        ctl = Controller()
    except Exception:
        guard.log_error("al abrir", *sys.exc_info())
        app.clipboard().setText(guard.report())
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None, "Holi tuvo un problema al abrirse.\n\nCopié el detalle: pégalo en el chat para revisarlo. "
                "También quedó en %APPDATA%\\HoliLite\\errores.txt.", C.APP_NAME, 0x30)
        return 1
    guard.register_restart()                 # si Windows lo ve cerrarse de golpe o colgarse, lo vuelve a abrir

    def on_new_connection():
        conn = server.nextPendingConnection()
        if not conn:
            return
        conn.waitForReadyRead(500)
        msg = bytes(conn.readAll()).decode(errors="ignore")
        conn.close()
        if msg == "replace":
            app.quit()
        else:
            ctl.show_blob()

    server.newConnection.connect(on_new_connection)
    app.aboutToQuit.connect(ctl.save)
    return app.exec()


def uninstall():
    """Desinstala Holi Lite (lo llama Windows desde Configuracion > Aplicaciones)."""
    import ctypes
    import os
    import shutil
    import subprocess
    import winreg
    from holi import settings

    def ask(text, flags):
        return ctypes.windll.user32.MessageBoxW(None, text, "Holi Lite", flags)

    if ask("¿Desinstalar Holi Lite?", 0x04 | 0x20) != 6:
        return 0
    already_running(replace=True)             # lo cierra si esta abierto (guarda al cerrarse)
    hidden = 0x08000000
    ps = ("foreach ($d in @([Environment]::GetFolderPath('Programs'), [Environment]::GetFolderPath('Desktop'))) "
          "{ Remove-Item -LiteralPath (Join-Path $d 'Holi Lite.lnk') -ErrorAction SilentlyContinue }")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], creationflags=hidden)
    autostart.set_enabled(False)
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\HoliLite")
    except OSError:
        pass
    if ask("¿Borrar también sus planetas, su confianza y tus ajustes?\n\n"
           "Si eliges No, quedan guardados por si lo vuelves a instalar.", 0x04 | 0x20) == 6:
        settings.qsettings().clear()
        shutil.rmtree(os.path.join(os.environ.get("APPDATA", ""), "HoliLite"), ignore_errors=True)
    # la carpeta del programa se borra cuando este proceso termine
    folder = os.path.dirname(sys.executable)
    if getattr(sys, "frozen", False) and os.path.basename(folder).lower() == "holi lite":
        subprocess.Popen('cmd /c ping -n 4 127.0.0.1 >nul & rmdir /s /q "%s"' % folder,
                         creationflags=hidden, close_fds=True, cwd=os.environ.get("TEMP"))
    ask("Holi Lite se desinstaló.", 0x40)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        guard.log_error("main", *sys.exc_info())
        sys.exit(1)
