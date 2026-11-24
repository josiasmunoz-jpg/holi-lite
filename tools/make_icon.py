"""Genera assets/blob.ico con el dibujo actual de Holi (el mismo del icono de la bandeja), en todos
los tamanos que usa Windows (16 a 256 px), cada uno dibujado a su tamano para que se vea nitido."""
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from holi.renderer import icon_pixmap  # noqa: E402

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def main():
    app = QGuiApplication(sys.argv)  # noqa: F841
    from PIL import Image
    out_dir = os.path.join(ROOT, "assets")
    os.makedirs(out_dir, exist_ok=True)
    images = []
    for s in SIZES:
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        icon_pixmap(s).save(buf, "PNG")
        images.append(Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA"))
    ico = os.path.join(out_dir, "blob.ico")
    images[-1].save(ico, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    print("Icono creado en", ico)
    return 0


if __name__ == "__main__":
    sys.exit(main())
