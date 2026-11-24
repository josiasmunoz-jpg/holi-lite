"""Ventana transparente y sin bordes que muestra a Holi. La logica la mueve el controlador."""
import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from . import config as C
from .model import BlobModel
from .renderer import draw_blob


def apply_window_flags(widget, on_top):
    flags = Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint
    if on_top:
        flags |= Qt.WindowStaysOnTopHint
    widget.setWindowFlags(flags)


class BlobWindow(QWidget):
    context_menu_requested = Signal(object)   # QPoint global
    clicked = Signal()
    double_clicked = Signal()

    def __init__(self, model: BlobModel, on_top=True):
        super().__init__(None)
        self.model = model
        self.paused = False
        self.setWindowTitle(C.APP_NAME)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        apply_window_flags(self, on_top)
        self.resize_for_model()
        self.place()

    def set_on_top(self, on):
        visible = self.isVisible()
        apply_window_flags(self, on)
        if visible:
            self.show()

    def resize_for_model(self):
        side = int(math.ceil(self.model.R * 6.8))    # espacio para gorro, zzz, corazones y planetas
        self.setFixedSize(side, side)

    def place(self):
        x = int(math.floor(self.model.x - self.width() / 2))
        y = int(math.floor(self.model.y - self.height() / 2))
        if x != self.x() or y != self.y():
            self.move(x, y)

    def paintEvent(self, _):
        p = QPainter(self)
        pose = self.model.pose()
        p.setOpacity(pose.get("alpha", 1.0))
        draw_blob(p, pose, self.model.x - self.x(), self.model.y - self.y())
        p.end()

    # ------------------------------------------------------------ mouse
    def _on_body(self, gx, gy):
        return math.hypot(gx - self.model.x, gy - self.model.y) <= self.model.R * 1.35

    def mousePressEvent(self, e):
        g = e.globalPosition()
        if e.button() in (Qt.LeftButton, Qt.RightButton) and self._on_body(g.x(), g.y()):
            self.model.press(g.x(), g.y())
        e.accept()

    def mouseMoveEvent(self, e):
        g = e.globalPosition()
        self.model.move_pointer(g.x(), g.y())
        if self.paused and self.model.mode == BlobModel.DRAG:
            self.model.x, self.model.y = self.model.drag_target     # pausado igual se puede mover
            self.place()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.RightButton:
            # clic derecho: si lo arrastraste, lo sueltas (igual que con el izquierdo); si no, abre el menu
            if self.model.mode == BlobModel.DRAG:
                self.model.release()
                if self.paused:
                    self.model.mode = BlobModel.IDLE
                    self.model.vx = self.model.vy = 0.0
            else:
                self.model.pressing = False
                self.context_menu_requested.emit(e.globalPosition().toPoint())
            self.update()
            e.accept()
            return
        if e.button() == Qt.LeftButton:
            result = self.model.release()
            if result == "click":
                self.clicked.emit()
            if self.paused:
                self.model.mode = BlobModel.IDLE
                self.model.vx = self.model.vy = 0.0
            self.update()
        e.accept()

    def mouseDoubleClickEvent(self, e):
        g = e.globalPosition()
        if e.button() == Qt.LeftButton and self._on_body(g.x(), g.y()):
            self.double_clicked.emit()
        e.accept()

    def contextMenuEvent(self, e):
        e.accept()                               # el menu se abre al soltar el clic derecho (ver arriba)
