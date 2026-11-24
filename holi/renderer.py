"""
Dibujo de Holi con QPainter: cuerpo plano, ojos redondos con parpados (para las
expresiones), boca (solo en la broma), sombra suave, planetas y particulas.
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient, QTransform)

from . import config as C
from .fx import draw_disk, draw_hat, draw_orbit, draw_particles


def body_path(R, wobble, t, n=48, lumps=None):
    """Contorno casi circular con una ondulacion muy leve (sensacion blanda).
    lumps: [(angulo, amplitud)] bultos (cachetes inflados con los planetas adentro)."""
    pts = []
    for i in range(n):
        th = 2 * math.pi * i / n
        w = 0.65 * math.sin(2 * th + 1.7 * t) + 0.35 * math.sin(3 * th - 1.3 * t + 1.3)
        r = R * (1.0 + wobble * w)
        if lumps:
            for ang, amp in lumps:
                d = (th - ang + math.pi) % (2 * math.pi) - math.pi
                r += R * amp * math.exp(-(d * d) / 0.09)
        pts.append((r * math.cos(th), r * math.sin(th)))
    path = QPainterPath(QPointF(*pts[0]))
    for i in range(n):           # Catmull-Rom -> Bezier: borde perfectamente suave
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = QPointF(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = QPointF(p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        path.cubicTo(c1, c2, QPointF(*p2))
    path.closeSubpath()
    return path


def _heart(size):
    """Corazon centrado en 0,0 (para la expresion de carino)."""
    s = size / 2
    path = QPainterPath(QPointF(0, s * 0.95))
    path.cubicTo(QPointF(-s * 1.25, s * 0.05), QPointF(-s * 0.75, -s * 1.05), QPointF(0, -s * 0.38))
    path.cubicTo(QPointF(s * 0.75, -s * 1.05), QPointF(s * 1.25, s * 0.05), QPointF(0, s * 0.95))
    return path


def _draw_eye(p, eye, side, R, eye_color, body_color):
    """Un ojo ovalado. Segun la emocion: arco (feliz), corazon, chevron (><) o con parpado."""
    w, h = eye["w"], eye["h"]
    shape = eye.get("shape", "ellipse")
    if shape == "chevron":
        s = R * 0.17
        pen = QPen(eye_color, max(1.4, R * 0.09))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        d = -side
        path = QPainterPath(QPointF(-d * s * 0.6, -s))
        path.lineTo(QPointF(d * s * 0.6, 0))
        path.lineTo(QPointF(-d * s * 0.6, s))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        return
    if shape == "heart":
        p.setBrush(eye_color)                    # ojos de corazon blancos (todo en blanco y negro)
        p.drawPath(_heart(max(w, h) * 1.05))
        return
    if shape == "arc":
        # ojo feliz: un arco grueso, como una sonrisa al reves
        pen = QPen(eye_color, max(1.6, w * 0.32))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        rw, rh = w * 0.82, h * 0.55
        p.drawArc(QRectF(-rw / 2, -rh / 2 + h * 0.08, rw, rh * 1.6), 20 * 16, 140 * 16)
        p.setPen(Qt.NoPen)
        return
    if shape == "line":
        # cerrado: rayita levemente curva
        pen = QPen(eye_color, max(1.4, R * 0.075))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        rw = w * 0.9
        p.drawArc(QRectF(-rw / 2, -R * 0.05, rw, R * 0.14), 200 * 16, 140 * 16)
        p.setPen(Qt.NoPen)
        return

    path = QPainterPath()
    path.addEllipse(QRectF(-w / 2, -h / 2, w, h))
    lid = eye.get("lid", 0.0)
    if lid > 0.02:
        # parpado: corta la parte de arriba, inclinado segun la emocion
        y0 = -h / 2 + lid * h
        cover = QPainterPath()
        cover.addRect(QRectF(-w * 3, y0 - h * 3, w * 6, h * 3))
        t = QTransform()
        t.translate(0, y0)
        t.rotate(-eye.get("lid_angle", 0.0) * side)
        t.translate(0, -y0)
        path = path.subtracted(t.map(cover))
    low = eye.get("low_lid", 0.0)
    if low > 0.02:
        # parpado inferior curvo (mejillas que suben: orgullo, verguenza)
        y1 = h / 2 - low * h
        cover = QPainterPath()
        cover.addEllipse(QRectF(-w * 0.9, y1, w * 1.8, h * 1.4))
        path = path.subtracted(cover)
    p.setBrush(eye_color)
    p.drawPath(path)


def _draw_mouth(p, shape, o, x, y, R, eye_color, t):
    """Boca de la broma: blanca entera, igual que los ojos. o = cuanto esta abierta (0..1)."""
    if o <= 0.02:
        return
    p.save()
    p.translate(x, y)
    p.setPen(Qt.NoPen)
    p.setBrush(eye_color)
    if shape == "o":                             # boca abierta para tragar o escupir
        rx, ry = R * (0.07 + 0.13 * o), R * (0.05 + 0.18 * o)
        p.drawEllipse(QPointF(0, ry * 0.2), rx, ry)
    elif shape == "smile":                       # sonrisa (traviesa o riendose)
        w = R * (0.2 + 0.14 * o)
        d = R * (0.05 + 0.15 * o)
        path = QPainterPath(QPointF(-w / 2, 0))
        path.lineTo(QPointF(w / 2, 0))
        path.cubicTo(QPointF(w / 2, d * 1.3), QPointF(-w / 2, d * 1.3), QPointF(-w / 2, 0))
        p.drawPath(path)
    else:                                        # "chew": boca cerrada masticando
        c = QColor(eye_color)
        c.setAlphaF(min(1.0, o))
        pen = QPen(c, max(1.4, R * 0.06))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        w = R * 0.22
        wob = math.sin(t * 14) * R * 0.03
        path = QPainterPath(QPointF(-w * 0.4, wob))
        path.quadTo(QPointF(0, -wob * 1.5 + R * 0.03), QPointF(w * 0.4, -wob))
        p.drawPath(path)
    p.restore()


def draw_blob(p: QPainter, pose, cx, cy, shadow=True, rim_alpha=None):
    R = pose["R"]
    rim_alpha = C.RIM_ALPHA if rim_alpha is None else rim_alpha
    body_color = QColor(*C.hex_rgb(C.S["body_color"]))
    eye_color = QColor(*C.hex_rgb(C.S["eye_color"]))
    p.setRenderHint(QPainter.Antialiasing, True)
    lift = pose["bob"] + pose.get("hop", 0.0)

    # sombra difusa, queda abajo mientras el cuerpo flota o salta
    if shadow and pose.get("shadow", True):
        up = max(0.0, -lift)
        a = int(C.SHADOW_ALPHA * (1.0 - min(0.6, up / (R * 1.2))))
        p.save()
        p.translate(cx, cy + R * 1.18)
        p.scale(1.0, 0.24)
        g = QRadialGradient(QPointF(0, 0), R * 0.95)
        g.setColorAt(0.0, QColor(0, 0, 0, a))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), R * 0.95, R * 0.95)
        p.restore()

    fx = pose.get("fx")
    orbit = pose.get("orbit")
    draw_orbit(p, orbit, cx, cy + lift, R, front=False)
    draw_disk(p, fx, cx, cy + lift, R, front=False)

    p.save()
    p.translate(cx, cy + lift)
    p.rotate(math.degrees(pose["lean"]))

    sx, sy = pose["stretch"]
    mag = math.hypot(sx, sy)
    if mag > 1e-4:                       # estirar en la direccion del movimiento
        ang = math.degrees(math.atan2(sy, sx))
        p.rotate(ang)
        p.scale(1 + mag, 1 / (1 + mag))
        p.rotate(-ang)
    q = pose["squash"] * 0.6             # aplastar / alargar conservando volumen
    p.scale(1 + q, 1 / (1 + q))
    b = pose["breath"]
    p.scale(1 - b * 0.6, 1 + b)

    path = body_path(R, pose["wobble"], pose["t"], lumps=pose.get("lumps"))
    pen = QPen(QColor(255, 255, 255, rim_alpha), 1.0)
    pen.setCosmetic(True)
    p.setPen(pen if rim_alpha > 0 else Qt.NoPen)
    p.setBrush(body_color)
    p.drawPath(path)

    # ojos proyectados sobre una esfera; nunca tocan el borde
    p.setPen(Qt.NoPen)
    yaw = max(-C.S["max_yaw"], min(C.S["max_yaw"], pose["yaw"]))
    pitch = max(-0.45, min(0.7, pose["pitch"]))
    wide = pose["wide"]
    eyes = pose.get("eyes") or [{}, {}]
    t = pose["t"]
    raw = []
    for idx, side in enumerate((-1, 1)):
        e = dict(eyes[idx])
        yi = yaw + side * C.EYE_SPREAD
        fore = 0.7 + 0.3 * max(0.0, math.cos(yi))     # ojos redondos: casi no se aplastan al girar
        vfore = max(0.7, math.cos(pitch * 0.8))
        ex = R * 0.72 * math.sin(yi) * math.cos(pitch * 0.5)
        ey = -R * 0.72 * math.sin(pitch) + R * 0.02
        scale = e.get("scale", 1.0)
        opened = e.get("open", pose.get("open", 1.0))
        h = R * C.EYE_HEIGHT * scale * vfore * (1 + 0.16 * wide)
        w = R * C.EYE_WIDTH * scale * fore * (1 + 0.16 * wide)
        if e.get("shape") in (None, "ellipse"):
            if opened < 0.3:
                e["shape"] = "line"
            else:
                h *= max(0.3, opened)
        e["w"], e["h"] = w, h
        raw.append([ex, ey, w, h, e, side])

    # los dos ojos se mueven juntos: si uno tocaria el borde, se acerca la cara completa al centro
    cx_f = (raw[0][0] + raw[1][0]) / 2
    cy_f = (raw[0][1] + raw[1][1]) / 2
    k = 1.0
    for ex, ey, w, h, e, side in raw:
        limit = R * 0.92 - max(h, w) / 2
        d = math.hypot(ex, ey)
        if d > limit > 0:
            # cuanto hay que mover el centro de la cara para que este ojo quede adentro
            dx, dy = ex - cx_f, ey - cy_f
            lo, hi = 0.0, 1.0
            for _ in range(20):
                mid = (lo + hi) / 2
                if math.hypot(cx_f * mid + dx, cy_f * mid + dy) <= limit:
                    lo = mid
                else:
                    hi = mid
            k = min(k, lo)
    placed = []
    for ex, ey, w, h, e, side in raw:
        ex = cx_f * k + (ex - cx_f)
        ey = cy_f * k + (ey - cy_f)
        roll = -(yaw * 14 + pitch * 4) + e.get("roll", 0.0)
        p.save()
        p.translate(ex, ey)
        p.rotate(roll)
        _draw_eye(p, e, side, R, eye_color, body_color)
        p.restore()
        placed.append((ex, ey, w, h))

    # boca (solo en los gestos)
    mouth = pose.get("mouth")
    if mouth and placed:
        mx = sum(pp[0] for pp in placed) / len(placed)
        my = sum(pp[1] for pp in placed) / len(placed) + R * 0.47
        _draw_mouth(p, mouth[0], mouth[1], mx, my, R, eye_color, t)

    # rubor: rayitas rosadas bajo los ojos
    blush = pose.get("blush", 0.0)
    if blush > 0.05:
        pen = QPen(QColor(eye_color.red(), eye_color.green(), eye_color.blue(), int(170 * min(1.0, blush))),
                   max(1.0, R * 0.045))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        for ex, ey, w, h in placed:
            by = ey + h * 0.62 + R * 0.05
            for k in (-1, 0, 1):
                bx = ex + k * R * 0.08
                p.drawLine(QPointF(bx + R * 0.025, by - R * 0.035), QPointF(bx - R * 0.025, by + R * 0.035))
        p.setPen(Qt.NoPen)

    # lagrimas que caen
    tears = pose.get("tears", 0.0)
    if tears > 0.05:
        p.setBrush(QColor(eye_color.red(), eye_color.green(), eye_color.blue(), int(230 * min(1.0, tears))))
        for i, (ex, ey, w, h) in enumerate(placed):
            for j in range(2):
                ph = (t * 0.9 + j * 0.5 + i * 0.25) % 1.0
                ty = ey + h * 0.45 + ph * R * 0.55
                rr = R * 0.055 * (1 - ph * 0.4)
                drop = QPainterPath()
                drop.addEllipse(QPointF(ex, ty), rr, rr * 1.3)
                p.drawPath(drop)

    draw_hat(p, pose.get("hat"), R, t)
    p.restore()
    draw_disk(p, fx, cx, cy + lift, R, front=True)
    draw_orbit(p, orbit, cx, cy + lift, R, front=True)
    draw_particles(p, fx, cx, cy + lift, R, body_color)


def default_pose(R):
    return {"R": R, "bob": 0.0, "hop": 0.0, "lean": 0.0, "stretch": (0.0, 0.0), "squash": 0.0,
            "breath": 0.0, "wobble": 0.0, "t": 0.0, "yaw": C.FACE_YAW, "pitch": C.FACE_PITCH,
            "open": 1.0, "happy": 0.0, "wide": 0.0, "eyes": [{}, {}],
            "blush": 0.0, "tears": 0.0}


def icon_pixmap(size=64):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    pose = default_pose(size * 0.44)
    # en el icono sale "extranado": cabeza ladeada, un ojo grande y el otro entrecerrado
    pose["yaw"], pose["pitch"] = 0.05, 0.22
    pose["lean"] = 0.17
    pose["eyes"] = [{"scale": 0.86, "lid": 0.34, "lid_angle": -16}, {"scale": 1.16}]
    draw_blob(p, pose, size / 2, size / 2, shadow=False, rim_alpha=110)
    p.end()
    return pm
