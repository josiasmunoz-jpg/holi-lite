"""Globito de texto sobre Holi: guia de la primera vez y el recordatorio de pausas.
Ventana aparte (no roba el foco ni los clics) que sigue a Holi y aparece y se va con un fundido."""
from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

BODY = QColor(22, 22, 26, 242)
TEXT = QColor(242, 242, 245)
TAIL = 7


class Tip(QWidget):
    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.font_ = QFont("Segoe UI", 1)
        self.font_.setPixelSize(13)
        self.text = ""
        self.anim = None
        self.hide_timer = QTimer(self, singleShot=True, timeout=self.dismiss)

    def say(self, text, secs=7.0):
        self.text = text
        fm = QFontMetrics(self.font_)
        lines = text.split("\n")
        w = max(fm.horizontalAdvance(t) for t in lines) + 28
        h = fm.height() * len(lines) + 16 + TAIL
        self.setFixedSize(int(w), int(h))
        self.update()
        self._fade(True)
        self.hide_timer.start(int(secs * 1000))

    def dismiss(self):
        if self.isVisible():
            self._fade(False)

    def follow(self, x, y_top):
        """Lo pone centrado sobre (x, y_top): y_top es el borde de arriba de Holi."""
        self.move(int(x - self.width() / 2), int(y_top - self.height()))

    def _fade(self, show):
        if self.anim:
            self.anim.stop()
        if show and not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
        self.anim = QPropertyAnimation(self, b"windowOpacity", self)
        self.anim.setDuration(350)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(1.0 if show else 0.0)
        if not show:
            self.anim.finished.connect(self.hide)
        self.anim.start()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height() - TAIL
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 12, 12)
        tail = QPainterPath(QPointF(w / 2 - TAIL, h - 1))
        tail.lineTo(QPointF(w / 2, h + TAIL - 1))
        tail.lineTo(QPointF(w / 2 + TAIL, h - 1))
        tail.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(BODY)
        p.drawPath(path.united(tail))
        p.setPen(TEXT)
        p.setFont(self.font_)
        p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, self.text)
