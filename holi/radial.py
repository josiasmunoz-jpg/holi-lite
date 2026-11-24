"""
Menu circular de Holi. Al abrirlo, el Holi real se desliza al centro de la pantalla y crece
un poco; el menu es un anillo negro (como su cuerpo) a su alrededor, con botones redondos y
su nombre debajo. Una pildora bajo el anillo dice que hace cada boton.

Todo es suave: el menu aparece y se va desvaneciendo, las paginas cambian con un fundido
girando, el resaltado del mouse y los textos se encienden y apagan de a poco.

La ventana cubre la pantalla (casi transparente, oscurece apenas) para poder cerrar con
animacion al hacer clic afuera. Holi queda por encima, en el hueco del anillo.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .fx import star_path

BODY = QColor(16, 16, 18)
TEXT = QColor(242, 242, 245)
DIM = QColor(242, 242, 245, 120)
HOLE_FILL = QColor(232, 234, 239, 235)

OUTER = 200             # radio exterior del anillo
HOLE = 98               # radio del hueco donde queda Holi
RING = 149              # radio donde van los botones
BTN = 23                # radio de cada boton


def _ease(k):
    k = max(0.0, min(1.0, k))
    return 1 - (1 - k) ** 3


def _font(px, bold=False):
    f = QFont("Segoe UI")
    f.setPixelSize(px)
    f.setBold(bold)
    return f


class Item:
    def __init__(self, label, icon, action=None, page=None, checked=None, color=None, keep_open=False,
                 state=None, short=None, glow=None):
        self.label = label          # nombre completo (en la pildora)
        self.icon = icon            # nombre del icono (ver _draw_icon) o "color"
        self.action = action        # que hace al hacer clic
        self.page = page            # o a que pagina lleva
        self.checked = checked      # None = no es interruptor
        self.color = color          # para muestras de color
        self.keep_open = keep_open  # no cerrar el menu despues de la accion
        self.state = state          # texto extra ("activado", "tiene hambre"...)
        self.short = short or label # nombre corto bajo el boton
        self.glow = glow            # color para resaltar el boton (hambre, sueno)


class RadialMenu(QWidget):
    def __init__(self, build_page, title_fn, on_close_start):
        super().__init__(None)
        self.build_page = build_page        # pagina -> (titulo, [Item])
        self.title_fn = title_fn            # () -> (linea1, linea2) en la pagina principal
        self.on_close_start = on_close_start
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
                            | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.center = QPointF(0, 0)
        self.stack = ["main"]
        self.items, self.old_items = [], []
        self.title = ""
        self.hover = -1
        self.hover_amt = []
        self.back_hot = 0.0
        self.t_open = 0.0
        self.closing = False
        self.t_page = 1.0
        self.clock = 0.0
        self.text = ("", "")
        self.old_text = ("", "")
        self.t_text = 1.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    # ------------------------------------------------------------ abrir / cerrar / navegar
    def open_around(self, cx, cy, screen_rect):
        """screen_rect: (x, y, w, h) de la pantalla donde se abre; cx, cy: centro (coordenadas globales)."""
        x, y, w, h = screen_rect
        self.setGeometry(int(x), int(y), int(w), int(h))
        self.center = QPointF(cx - x, cy - y)
        self.stack = ["main"]
        self.title, self.items = self.build_page("main")
        self.old_items = []
        self.hover_amt = [0.0] * len(self.items)
        self.hover = -1
        self.t_page = 1.0
        self.t_open = 0.0 if not self.isVisible() else self.t_open
        self.closing = False
        self.text = self._current_text()
        self.t_text = 1.0
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.timer.start(16)

    def close_smooth(self):
        if self.closing or not self.isVisible():
            return
        self.closing = True
        self.on_close_start()

    def refresh(self):
        self.title, self.items = self.build_page(self.stack[-1])
        self.hover_amt = (self.hover_amt + [0.0] * len(self.items))[:len(self.items)]
        self._set_text(self._current_text())

    def go(self, page):
        self.stack.append(page)
        self._change_page()

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self._change_page()
        else:
            self.close_smooth()

    def _change_page(self):
        self.old_items = self.items
        self.title, self.items = self.build_page(self.stack[-1])
        self.hover_amt = [0.0] * len(self.items)
        self.hover = -1
        self.t_page = 0.0
        self._set_text(self._current_text())

    def _tick(self):
        dt = 0.016
        self.clock += dt
        if self.closing:
            self.t_open = max(0.0, self.t_open - dt / 0.2)
            if self.t_open <= 0:
                self.timer.stop()
                self.hide()
                self.closing = False
                return
        else:
            self.t_open = min(1.0, self.t_open + dt / 0.24)
        self.t_page = min(1.0, self.t_page + dt / 0.32)
        self.t_text = min(1.0, self.t_text + dt / 0.18)
        k = 1 - math.exp(-dt * 14)
        for i in range(len(self.hover_amt)):
            target = 1.0 if i == self.hover else 0.0
            self.hover_amt[i] += (target - self.hover_amt[i]) * k
        self.back_hot += ((1.0 if self._back_hover else 0.0) - self.back_hot) * k
        new = self._current_text()
        if new != self.text:
            self._set_text(new)
        self.update()

    _back_hover = False

    # ------------------------------------------------------------ textos
    def _current_text(self):
        if self.hover >= 0 and self.hover < len(self.items):
            it = self.items[self.hover]
            return (it.label, it.state or ("activado" if it.checked else "desactivado" if it.checked is False else ""))
        if len(self.stack) == 1:
            return self.title_fn()
        return (self.title, "")

    def _set_text(self, t):
        if t == self.text:
            return
        self.old_text = self.text
        self.text = t
        self.t_text = 0.0

    # ------------------------------------------------------------ geometria
    def _pos(self, i, n=None):
        n = n or max(1, len(self.items))
        a = -math.pi / 2 + 2 * math.pi * i / n
        return QPointF(self.center.x() + math.cos(a) * RING, self.center.y() + math.sin(a) * RING)

    def _dist(self, p):
        return math.hypot(p.x() - self.center.x(), p.y() - self.center.y())

    def _hit(self, p):
        for i in range(len(self.items)):
            q = self._pos(i)
            if math.hypot(p.x() - q.x(), p.y() - q.y()) <= BTN + 6:
                return i
            if abs(p.x() - q.x()) <= 34 and 0 <= p.y() - q.y() - BTN <= 20:
                return i
        return -1

    def _back_rect(self):
        c = self.center
        return QRectF(c.x() - 52, c.y() - OUTER - 44, 104, 30)

    # ------------------------------------------------------------ mouse / teclado
    def mouseMoveEvent(self, e):
        if self.closing:
            return
        p = e.position()
        h = self._hit(p) if self.t_page > 0.5 else -1
        self._back_hover = len(self.stack) > 1 and self._back_rect().contains(p)
        if h != self.hover:
            self.hover = h
        self.setCursor(Qt.PointingHandCursor if (h >= 0 or self._back_hover) else Qt.ArrowCursor)

    def mousePressEvent(self, e):
        if self.closing:
            return
        p = e.position()
        if e.button() == Qt.RightButton:
            self.back()
            return
        if len(self.stack) > 1 and self._back_rect().contains(p):
            self.back()
            return
        d = self._dist(p)
        if d > OUTER + 4:
            self.close_smooth()
            return
        if d < HOLE:
            if len(self.stack) > 1:
                self.back()
            return
        i = self._hit(p)
        if i >= 0 and self.t_page > 0.5:
            it = self.items[i]
            if it.page:
                self.go(it.page)
            elif it.action:
                if not it.keep_open:
                    self.close_smooth()
                it.action()
                if it.keep_open and self.isVisible() and not self.closing:
                    self.refresh()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_smooth()
        elif e.key() in (Qt.Key_Backspace, Qt.Key_Left):
            self.back()

    # ------------------------------------------------------------ dibujo
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        ease = _ease(self.t_open)
        c = self.center

        # fondo: oscurece apenas (y captura los clics para cerrar con animacion)
        p.fillRect(self.rect(), QColor(0, 0, 0, int(2 + 46 * ease)))

        p.save()
        p.setOpacity(ease)
        p.translate(c)
        s = 0.88 + 0.12 * ease
        p.scale(s, s)
        p.rotate((1 - ease) * -12)
        p.translate(-c)

        # anillo negro con el borde suave de Holi (hueco al centro para el Holi real)
        ring = QPainterPath()
        ring.addEllipse(c, OUTER, OUTER)
        hole = QPainterPath()
        hole.addEllipse(c, HOLE, HOLE)
        ring = ring.subtracted(hole)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BODY.red(), BODY.green(), BODY.blue(), 240))
        p.drawPath(ring)
        p.setBrush(HOLE_FILL)                    # hueco claro: Holi negro se ve con cualquier fondo de pantalla
        p.drawEllipse(c, HOLE, HOLE)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1.2))
        p.drawEllipse(c, OUTER, OUTER)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
        p.drawEllipse(c, HOLE, HOLE)

        # botones: la pagina anterior se va desvaneciendo y la nueva entra girando
        kp = self.t_page
        if self.old_items and kp < 1:
            out = max(0.0, 1 - kp / 0.45)
            for i, it in enumerate(self.old_items):
                q = self._pos(i, len(self.old_items))
                q = self._rot(q, kp * 0.5)
                p.setOpacity(ease * out)
                self._draw_button(p, q, it, 0.0, 0.85 + 0.15 * out)
        kin = _ease((kp - 0.25) / 0.75)
        for i, it in enumerate(self.items):
            q = self._rot(self._pos(i), (1 - kin) * -0.45)
            p.setOpacity(ease * kin)
            amt = self.hover_amt[i] if i < len(self.hover_amt) else 0.0
            self._draw_button(p, q, it, amt, 0.8 + 0.2 * kin)
        p.restore()

        # pildora con el texto (bajo el anillo) y boton volver (sobre el anillo)
        p.setOpacity(ease)
        self._draw_caption(p, c)
        if len(self.stack) > 1 or (self.old_items and kp < 1 and len(self.stack) > 1):
            self._draw_back(p)
        p.end()

    def _rot(self, q, ang):
        c = self.center
        dx, dy = q.x() - c.x(), q.y() - c.y()
        return QPointF(c.x() + dx * math.cos(ang) - dy * math.sin(ang),
                       c.y() + dx * math.sin(ang) + dy * math.cos(ang))

    def _draw_button(self, p, q, it, hot, scale):
        p.save()
        p.translate(q)
        p.scale(scale, scale)
        z = QPointF(0, 0)
        if it.glow is not None:              # resaltado que late (hambre, sueno)
            g = QColor(it.glow)
            pulse = 0.5 + 0.5 * math.sin(self.clock * 4.0)
            g.setAlphaF(0.16 + 0.22 * pulse)
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(z, BTN + 7 + 3 * pulse, BTN + 7 + 3 * pulse)
        if hot > 0.01:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, int(36 * hot)))
            p.drawEllipse(z, BTN + 4 * hot, BTN + 4 * hot)
        # encendido: boton blanco con icono negro (como sus ojos); apagado: negro con icono blanco
        filled = it.checked is True and it.icon != "color"
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(TEXT if filled else QColor(28, 28, 32))
        r = BTN * (1 + 0.06 * hot)
        p.drawEllipse(z, r, r)
        if (it.checked and not filled) or it.glow is not None:   # color elegido o resaltado: anillo blanco
            p.setPen(QPen(TEXT, 2.0))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(z, r - 1.5, r - 1.5)
        _draw_icon(p, it.icon, QColor(BODY if filled else TEXT), it.color)
        # nombre corto bajo el boton
        f = _font(10, it.glow is not None)
        p.setFont(f)
        tc = QColor(TEXT)
        tc.setAlpha(min(255, int(200 + 55 * hot)))
        p.setPen(tc)
        p.drawText(QRectF(-50, BTN + 3, 100, 14), Qt.AlignHCenter | Qt.AlignTop,
                   QFontMetrics(f).elidedText(it.short, Qt.ElideRight, 98))
        p.restore()

    def _draw_caption(self, p, c):
        k = _ease(self.t_text)
        y = c.y() + OUTER + 14
        for (l1, l2), a in ((self.old_text, 1 - k), (self.text, k)):
            if a <= 0.01 or not l1:
                continue
            f1, f2 = _font(13, True), _font(11)
            w = max(QFontMetrics(f1).horizontalAdvance(l1), QFontMetrics(f2).horizontalAdvance(l2) if l2 else 0)
            w = min(420, w + 40)
            h = 46 if l2 else 30
            rect = QRectF(c.x() - w / 2, y + (1 - a) * 4, w, h)
            p.save()
            p.setOpacity(p.opacity() * a)
            p.setPen(QPen(QColor(255, 255, 255, 30), 1))
            p.setBrush(QColor(BODY.red(), BODY.green(), BODY.blue(), 235))
            p.drawRoundedRect(rect, h / 2, h / 2)
            p.setPen(TEXT)
            p.setFont(f1)
            p.drawText(QRectF(rect.x(), rect.y() + 6, w, 18), Qt.AlignCenter,
                       QFontMetrics(f1).elidedText(l1, Qt.ElideRight, int(w - 24)))
            if l2:
                p.setPen(DIM)
                p.setFont(f2)
                p.drawText(QRectF(rect.x(), rect.y() + 24, w, 16), Qt.AlignCenter,
                           QFontMetrics(f2).elidedText(l2, Qt.ElideRight, int(w - 24)))
            p.restore()

    def _draw_back(self, p):
        r = self._back_rect()
        h = self.back_hot
        p.setPen(QPen(QColor(255, 255, 255, int(30 + 40 * h)), 1))
        p.setBrush(QColor(int(16 + 20 * h), int(16 + 20 * h), int(18 + 22 * h), 235))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(TEXT)
        p.setFont(_font(12, True))
        p.drawText(r, Qt.AlignCenter, "‹  Volver")


# ====================================================================== iconos
def _pen(col, w=1.8):
    pen = QPen(col, w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _draw_icon(p, name, col, color=None):
    p.setPen(_pen(col))
    p.setBrush(Qt.NoBrush)
    if name == "color":                      # muestra de color: borde claro para que se vean los oscuros
        p.setPen(QPen(QColor(255, 255, 255, 150), 1.4))
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(0, 0), 10, 10)
    elif name == "food":
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPath(star_path(10))
    elif name == "sleep":
        full = QPainterPath()
        full.addEllipse(QPointF(0, 0), 9, 9)
        bite = QPainterPath()
        bite.addEllipse(QPointF(5, -4), 7.5, 7.5)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPath(full.subtracted(bite))
    elif name == "planets":
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(0, 0), 5, 5)
        p.setPen(_pen(col, 1.5))
        p.setBrush(Qt.NoBrush)
        p.save()
        p.rotate(-18)
        p.drawEllipse(QPointF(0, 0), 11, 4)
        p.restore()
    elif name == "hide":                     # ojo cerrado
        path = QPainterPath(QPointF(-10, 0))
        path.quadTo(QPointF(0, 7), QPointF(10, 0))
        p.drawPath(path)
        for x in (-6, 0, 6):
            p.drawLine(QPointF(x, 5), QPointF(x * 1.2, 8))
    elif name == "pause":
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(-6, -7, 4, 14), 1.5, 1.5)
        p.drawRoundedRect(QRectF(2, -7, 4, 14), 1.5, 1.5)
    elif name == "pin":
        path = QPainterPath(QPointF(-8, 2))
        path.lineTo(QPointF(-8, 8))
        path.lineTo(QPointF(-2, 8))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(2, -2), 5, 5)
    elif name == "size":
        p.drawEllipse(QPointF(0, 0), 10, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(0, 0), 4.5, 4.5)
    elif name in ("small", "medium", "large"):
        r = {"small": 4.5, "medium": 7, "large": 10}[name]
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(0, 0), r, r)
    elif name == "options":
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        for x in (-7, 0, 7):
            p.drawEllipse(QPointF(x, 0), 2.4, 2.4)
    elif name == "exit":
        p.drawLine(QPointF(-6, -6), QPointF(6, 6))
        p.drawLine(QPointF(6, -6), QPointF(-6, 6))
    elif name == "sound":
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        path = QPainterPath(QPointF(-9, -3))
        for pt in ((-5, -3), (0, -8), (0, 8), (-5, 3), (-9, 3)):
            path.lineTo(QPointF(*pt))
        path.closeSubpath()
        p.drawPath(path)
        p.setPen(_pen(col, 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawArc(QRectF(-2, -5, 8, 10), -50 * 16, 100 * 16)
        p.drawArc(QRectF(-2, -9, 13, 18), -50 * 16, 100 * 16)
    elif name == "music":                      # corchea doble
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(-5, 6), 3.6, 2.8)
        p.drawEllipse(QPointF(6, 4), 3.6, 2.8)
        p.setPen(_pen(col, 1.8))
        p.drawLine(QPointF(-1.6, 6), QPointF(-1.6, -7))
        p.drawLine(QPointF(9.4, 4), QPointF(9.4, -9))
        p.setPen(_pen(col, 3.0))
        p.drawLine(QPointF(-1.6, -7), QPointF(9.4, -9))
    elif name == "hat":
        path = QPainterPath(QPointF(-9, 7))
        path.lineTo(QPointF(0, -9))
        path.lineTo(QPointF(9, 7))
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPath(path)
    elif name == "perch":
        p.drawRoundedRect(QRectF(-10, -1, 20, 10), 2, 2)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(0, -6), 4.5, 4.5)
    elif name == "clock":
        p.drawEllipse(QPointF(0, 0), 9.5, 9.5)
        p.drawLine(QPointF(0, 0), QPointF(0, -6))
        p.drawLine(QPointF(0, 0), QPointF(4, 2))
    elif name == "fullscreen":
        for sx in (-1, 1):
            for sy in (-1, 1):
                path = QPainterPath(QPointF(sx * 9, sy * 4))
                path.lineTo(QPointF(sx * 9, sy * 9))
                path.lineTo(QPointF(sx * 4, sy * 9))
                p.drawPath(path)
    elif name == "ontop":
        p.drawRoundedRect(QRectF(-9, -2, 14, 10), 2, 2)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(-5, -8, 14, 10), 2, 2)
    elif name == "power":
        p.drawArc(QRectF(-8, -7, 16, 16), 125 * 16, -250 * 16)
        p.drawLine(QPointF(0, -9), QPointF(0, -1))
    elif name == "update":                   # flecha hacia abajo sobre una bandeja
        p.drawLine(QPointF(0, -9), QPointF(0, 3))
        p.drawLine(QPointF(-5, -2), QPointF(0, 3))
        p.drawLine(QPointF(5, -2), QPointF(0, 3))
        p.drawLine(QPointF(-9, 4), QPointF(-9, 8))
        p.drawLine(QPointF(-9, 8), QPointF(9, 8))
        p.drawLine(QPointF(9, 8), QPointF(9, 4))
    elif name == "report":                   # aviso: circulo con signo de exclamacion
        p.drawEllipse(QPointF(0, 0), 9, 9)
        p.drawLine(QPointF(0, -5), QPointF(0, 1))
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(0, 4.6), 1.4, 1.4)
    elif name == "name":                     # etiqueta con su nombre
        path = QPainterPath(QPointF(-9, -5))
        path.lineTo(QPointF(4, -5))
        path.lineTo(QPointF(10, 0))
        path.lineTo(QPointF(4, 5))
        path.lineTo(QPointF(-9, 5))
        path.closeSubpath()
        p.drawPath(path)
        p.drawEllipse(QPointF(3, 0), 1.4, 1.4)
    elif name == "break":                    # tacita con vapor
        p.drawRoundedRect(QRectF(-8, -2, 12, 10), 2, 2)
        p.drawArc(QRectF(2, 0, 7, 6), -90 * 16, 180 * 16)
        for x in (-5, -1):
            p.drawLine(QPointF(x, -5), QPointF(x + 1, -9))
    elif name == "custom":
        p.setPen(Qt.NoPen)
        for i, hexc in enumerate(("#ff8a3d", "#5ec8ff", "#a77bff", "#5fd68a")):
            a = i * math.pi / 2 + math.pi / 4
            p.setBrush(QColor(hexc))
            p.drawEllipse(QPointF(math.cos(a) * 5, math.sin(a) * 5), 4, 4)
