"""Aviso de version nueva: revisa en GitHub si hay un instalador mas nuevo (al abrir y una vez al dia).
Si lo hay, Holi avisa y en Opciones aparece "Actualizar": baja el instalador y lo corre en silencio
(cierra Holi, lo reemplaza y lo vuelve a abrir con tus planetas intactos). Nada se baja sin que lo pidas.
"""
import json
import os
import subprocess
import tempfile
import threading
import urllib.request

from . import __version__
from . import config as C

API = "https://api.github.com/repos/%s/releases/latest"


def _ver(text):
    try:
        return tuple(int(p) for p in str(text).lstrip("vV").split(".")[:3])
    except ValueError:
        return (0,)


class Updater:
    def __init__(self):
        self.latest = None            # {"version", "url", "page"} si hay una mas nueva
        self.busy = False

    def check(self):
        """Revisa en segundo plano. Sin internet o sin publicaciones: no pasa nada."""
        if self.busy or not C.GITHUB_REPO:
            return
        self.busy = True
        threading.Thread(target=self._check, daemon=True).start()

    def _check(self):
        try:
            req = urllib.request.Request(API % C.GITHUB_REPO, headers={
                "Accept": "application/vnd.github+json", "User-Agent": "HoliLite/" + __version__})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.load(r)
            tag = data.get("tag_name", "")
            asset = next((a for a in data.get("assets", []) if a.get("name", "").lower().endswith(".exe")), None)
            if asset and _ver(tag) > _ver(__version__):
                self.latest = {"version": tag.lstrip("vV"), "url": asset["browser_download_url"],
                               "page": data.get("html_url", "")}
        except Exception:
            pass
        finally:
            self.busy = False

    def install(self, on_error):
        """Baja el instalador nuevo y lo corre en silencio. on_error(texto) si algo falla."""
        if not self.latest:
            return
        info = self.latest

        def work():
            try:
                path = os.path.join(tempfile.gettempdir(), "HoliLite-Setup-%s.exe" % info["version"])
                req = urllib.request.Request(info["url"], headers={"User-Agent": "HoliLite/" + __version__})
                with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as out:
                    while True:
                        chunk = r.read(1 << 16)
                        if not chunk:
                            break
                        out.write(chunk)
                env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("_PYI", "_MEI"))}
                env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
                subprocess.Popen([path, "--silencioso"], close_fds=True, env=env)
            except Exception as exc:
                on_error(str(exc))
        threading.Thread(target=work, daemon=True).start()
