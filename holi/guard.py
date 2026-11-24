"""Que Holi no se caiga: los errores se anotan en errores.txt y Holi sigue vivo.

- guard(fn): envuelve lo que corre solo (el reloj de 60 fps, el corazon, la revision de pantalla
  completa). Si falla, se salta ese momento y sigue.
- install(): todo error que se escape (por ejemplo al apretar un boton del menu) va a errores.txt
  en vez de mostrar una ventana o cerrar Holi.
- register_restart(): si Windows ve que Holi se cerro de golpe o se colgo, lo vuelve a abrir.
- report(): texto listo para pegar (version, Windows y los ultimos errores).
"""
import datetime
import functools
import os
import platform
import sys
import time
import traceback

from . import __version__

FOLDER = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "HoliLite")
LOG = os.path.join(FOLDER, "errores.txt")
MAX_BYTES = 200_000                 # el archivo nunca pasa de ~200 KB: guarda lo mas nuevo
SAME_ERROR_EVERY = 60.0             # el mismo error se anota como mucho una vez por minuto

count = 0                           # errores en esta sesion (para las pruebas)
_last = {}


def log_error(where, exc_type, exc, tb):
    """Anota un error. Nunca lanza otro error."""
    global count
    count += 1
    try:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        key = (where, text.strip().splitlines()[-1] if text.strip() else "")
        now = time.monotonic()
        if now - _last.get(key, -1e9) < SAME_ERROR_EVERY:
            return
        _last[key] = now
        os.makedirs(FOLDER, exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > MAX_BYTES:
            with open(LOG, "rb") as fh:
                fh.seek(-MAX_BYTES // 2, os.SEEK_END)
                keep = fh.read()
            with open(LOG, "wb") as fh:
                fh.write(b"(...)\n" + keep)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("\n=== %s · %s · v%s ===\n" % (datetime.datetime.now().isoformat(timespec="seconds"),
                                                 where, __version__))
            fh.write(text)
    except Exception:
        pass


def guard(fn, where=None):
    """Version de fn que, si falla, anota el error y sigue."""
    name = where or getattr(fn, "__name__", "?")

    @functools.wraps(fn)
    def safe(*args, **kw):
        try:
            return fn(*args, **kw)
        except Exception:
            log_error(name, *sys.exc_info())
            return None
    return safe


def install():
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log_error("evento", exc_type, exc, tb)
    sys.excepthook = hook


def register_restart():
    """Windows lo vuelve a abrir si se cierra de golpe o se cuelga (no al reiniciar ni al actualizar)."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    try:
        import ctypes
        RESTART_NO_PATCH, RESTART_NO_REBOOT = 4, 8
        ctypes.windll.kernel32.RegisterApplicationRestart("--reabierto", RESTART_NO_PATCH | RESTART_NO_REBOOT)
    except Exception:
        pass


def report():
    """Texto para pegar en el chat: version, Windows y los ultimos errores."""
    head = "Holi Lite %s · %s %s · Python %s" % (__version__, platform.system(), platform.release(),
                                                 platform.python_version())
    try:
        with open(LOG, encoding="utf-8") as fh:
            body = fh.read()[-6000:]
    except OSError:
        body = ""
    return head + "\n" + (body.strip() or "Sin errores anotados.")


def has_errors():
    return os.path.exists(LOG) and os.path.getsize(LOG) > 0
