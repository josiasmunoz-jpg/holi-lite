"""
Efectos visuales de Holi:
- Particulas de emocion (Zzz al dormir, corazones con caricias, gotita de sudor si lo zamarreas,
  nubecita cuando se enoja, "?" cuando esta extrañado, globito con lo que necesita).
- Disco de agujero negro: un anillo de particulas que gira cuando celebra o come.
- Planetas en orbita (y la broma de tragarselos).
- Accesorios segun la fecha (gorro navideño, gorro de fiesta, banderita, sombrero de bruja).
"""
import datetime as dt
import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen, QTransform

from . import config as C


# ====================================================================== particulas
class Particles:
    """Vive dentro del modelo. Las posiciones son relativas al centro del blob (px)."""

    def __init__(self):
        self.items = []
        self.timers = {}
        self.disk = 0.0             # intensidad del disco de agujero negro
        self.disk_phase = 0.0
        self.want = None           # "hunger" o "sleep": globito con lo que necesita
        self.want_t = 0.0

    def _every(self, key, secs, dt):
        t = self.timers.get(key, 0.0) - dt
        if t <= 0:
            self.timers[key] = secs
            return True
        self.timers[key] = t
        return False

    def emit(self, kind, R, **kw):
        p = {"k": kind, "t": 0.0}
        if kind == "z":
            p.update(x=R * 0.55, y=-R * 0.95, vx=R * 0.12, vy=-R * 0.38, life=2.6, s=R * 0.26, ph=random.random() * 6)
        elif kind == "heart":
            p.update(x=random.uniform(-0.5, 0.5) * R, y=-R * 0.85, vx=random.uniform(-0.2, 0.2) * R,
                     vy=-R * random.uniform(0.55, 0.8), life=1.5, s=R * random.uniform(0.24, 0.34),
                     ph=random.random() * 6)
        elif kind == "sweat":
            side = random.choice((-1, 1))
            p.update(x=side * R * 0.88, y=-R * 0.55, vx=side * R * 0.25, vy=R * 0.1, life=0.9, s=R * 0.16, ph=0)
        elif kind == "puff":
            p.update(x=random.uniform(-0.35, 0.35) * R, y=-R * 1.1, vx=random.uniform(-0.15, 0.15) * R,
                     vy=-R * 0.35, life=0.9, s=R * 0.16, ph=0)
        elif kind == "snack":                  # estrellita de comida que cae y se traga
            p.update(x=R * 0.15, y=-R * 2.3, vx=-R * 0.3, vy=R * 3.6, life=0.62, s=R * 0.3, ph=0)
        elif kind == "pop":                    # estallido al escupir un planeta (desde la boca)
            a = kw.get("a", random.uniform(0, 2 * math.pi))
            sp = R * random.uniform(1.2, 2.0)
            mo = kw.get("at", (0.0, 0.38))
            p.update(x=mo[0] * R, y=mo[1] * R, vx=math.cos(a) * sp, vy=math.sin(a) * sp, life=0.45,
                     s=R * random.uniform(0.04, 0.07), ph=0)
        elif kind == "q":                      # "?" de extranado
            p.update(x=R * 0.75, y=-R * 1.0, vx=R * 0.08, vy=-R * 0.22, life=2.2, s=R * 0.5, ph=0)
        elif kind == "gift":                   # estrellita de regalo: aparece, flota y brilla
            p.update(x=R * 0.9, y=-R * 0.9, vx=R * 0.05, vy=-R * 0.25, life=2.8, s=R * 0.26, ph=random.random() * 6)
        elif kind == "snow":                   # copo: cae en toda la ventana, meciendose
            p.update(x=random.uniform(-3.2, 3.2) * R, y=-3.4 * R, vx=random.uniform(-0.1, 0.1) * R,
                     vy=R * random.uniform(0.7, 1.1), life=6.5, s=R * random.uniform(0.035, 0.07),
                     ph=random.random() * 6)
        elif kind == "fw":                     # chispa de fuego artificial (cae un poco)
            a = kw.get("a", random.uniform(0, 2 * math.pi))
            sp = R * random.uniform(1.4, 2.0)
            at = kw.get("at", (0.0, -2.0))
            p.update(x=at[0] * R, y=at[1] * R, vx=math.cos(a) * sp, vy=math.sin(a) * sp,
                     life=random.uniform(0.9, 1.3), s=R * 0.06, ph=0)
        elif kind == "spark":
            a = kw.get("a", random.uniform(0, 2 * math.pi))
            sp = kw.get("sp", R * random.uniform(1.6, 2.6))
            p.update(x=math.cos(a) * R * 0.9, y=math.sin(a) * R * 0.9, vx=math.cos(a) * sp, vy=math.sin(a) * sp,
                     life=0.55, s=R * 0.07, ph=0)
        p.update(kw.get("extra", {}))
        self.items.append(p)
        if len(self.items) > 120:
            del self.items[:-120]

    def burst(self, R, n=14):
        for i in range(n):
            self.emit("spark", R, a=2 * math.pi * i / n + random.uniform(-0.15, 0.15))

    def update(self, m, dt):
        R = m.R
        e = m.expr
        if m.asleep and self._every("z", 1.8, dt):
            self.emit("z", R)
        if m.pet > 0.6 and self._every("heart", 0.42, dt):
            self.emit("heart", R)
        if (m.dizzy_t > 0 or m.shake > 3.5) and self._every("sweat", 0.45, dt):
            self.emit("sweat", R)
        if e["angry"] > 0.5 and self._every("puff", 0.28, dt):
            self.emit("puff", R)
        if m.snow_t > 0:
            m.snow_t = max(0.0, m.snow_t - dt)
            if self._every("snow", 0.16, dt):
                self.emit("snow", R)
        if m.fireworks_t > 0:
            m.fireworks_t = max(0.0, m.fireworks_t - dt)
            if self._every("fw", 0.55, dt):
                at = (random.uniform(-2.4, 2.4), random.uniform(-2.9, -1.6))
                n = 18
                for i in range(n):
                    self.emit("fw", R, at=at, a=2 * math.pi * i / n + random.uniform(-0.1, 0.1))
        for p in self.items:
            p["t"] += dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            if p["k"] == "sweat":
                p["vy"] += R * 2.2 * dt
            elif p["k"] == "snow":
                p["x"] += math.sin(p["t"] * 1.7 + p["ph"]) * R * 0.25 * dt
            elif p["k"] == "fw":
                p["vx"] *= math.exp(-2.5 * dt)
                p["vy"] = p["vy"] * math.exp(-2.5 * dt) + R * 0.9 * dt
            elif p["k"] in ("spark", "pop"):
                p["vx"] *= math.exp(-4 * dt)
                p["vy"] *= math.exp(-4 * dt)
        self.items = [p for p in self.items if p["t"] < p["life"]]
        self.want_t = max(0.0, self.want_t - dt)
        target = 1.0 if (m.celebrate_t > 0 or m.gulp_t > 0) else 0.0
        self.disk += (target - self.disk) * min(1.0, dt * (5.0 if target else 2.2))
        self.disk_phase += dt * (2.2 + 2.5 * self.disk)

    def busy(self):
        return bool(self.items) or self.disk > 0.02 or self.want_t > 0

    def pose(self):
        return {"items": [dict(p) for p in self.items], "disk": self.disk, "disk_phase": self.disk_phase,
                "want": self.want if self.want_t > 0 else None, "want_t": self.want_t}


def _heart_path(size):
    s = size / 2
    path = QPainterPath(QPointF(0, s * 0.95))
    path.cubicTo(QPointF(-s * 1.25, s * 0.05), QPointF(-s * 0.75, -s * 1.05), QPointF(0, -s * 0.38))
    path.cubicTo(QPointF(s * 0.75, -s * 1.05), QPointF(s * 1.25, s * 0.05), QPointF(0, s * 0.95))
    return path


def star_path(r, inner=0.48, points=5):
    path = QPainterPath()
    for i in range(points * 2):
        a = -math.pi / 2 + math.pi * i / points
        rr = r if i % 2 == 0 else r * inner
        pt = QPointF(math.cos(a) * rr, math.sin(a) * rr)
        if i == 0:
            path.moveTo(pt)
        else:
            path.lineTo(pt)
    path.closeSubpath()
    return path


def _moon_path(r):
    full = QPainterPath()
    full.addEllipse(QPointF(0, 0), r, r)
    bite = QPainterPath()
    bite.addEllipse(QPointF(r * 0.55, -r * 0.35), r * 0.85, r * 0.85)
    return full.subtracted(bite)


def _outlined_text(painter, x, y, text, px, fill, alpha):
    """Texto con relleno oscuro y borde claro: se ve sobre fondos claros y oscuros."""
    f = QFont("Segoe UI", 1)
    f.setPixelSize(max(6, int(px)))
    f.setBold(True)
    path = QPainterPath()
    path.addText(QPointF(x, y), f, text)
    edge = QColor(255, 255, 255)
    edge.setAlphaF(0.9 * alpha)
    body = QColor(fill)
    body.setAlphaF(alpha)
    painter.setPen(QPen(edge, max(2.5, px * 0.22), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(edge)
    painter.drawPath(path)                       # halo claro
    painter.setPen(Qt.NoPen)
    painter.setBrush(body)
    painter.drawPath(path)                       # letra oscura encima


def _fade(p):
    t = p["t"] / p["life"]
    return min(1.0, t * 6) * (1.0 - max(0.0, (t - 0.6) / 0.4))


def _bw(painter, a, body_color, w=1.3):
    """Estilo de Holi para todo lo que sale de el: negro con borde blanco (se ve en fondos claros y oscuros)."""
    edge = QColor(255, 255, 255)
    edge.setAlphaF(0.95 * a)
    pen = QPen(edge, w)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    fill = QColor(body_color)
    fill.setAlphaF(a)
    painter.setBrush(fill)


def draw_particles(painter, fx, cx, cy, R, body_color=QColor(16, 16, 18)):
    """Particulas y globito sobre la cabeza. Se dibuja despues del cuerpo."""
    if not fx:
        return
    painter.save()
    painter.translate(cx, cy)
    painter.setPen(Qt.NoPen)
    for p in fx["items"]:
        a = _fade(p)
        k = p["k"]
        x = p["x"] + (math.sin(p["t"] * 3 + p["ph"]) * R * 0.08 if k in ("z", "heart") else 0)
        y = p["y"]
        if k == "z":
            size = p["s"] * (0.9 + 0.9 * p["t"] / p["life"])
            _outlined_text(painter, x, y, "z", size, body_color, a)
        elif k == "heart":
            _bw(painter, a, body_color)
            painter.save()
            painter.translate(x, y)
            painter.drawPath(_heart_path(p["s"]))
            painter.restore()
            painter.setPen(Qt.NoPen)
        elif k == "sweat":
            _bw(painter, 0.9 * a, body_color, 1.1)
            s = p["s"]
            path = QPainterPath(QPointF(x, y - s))
            path.cubicTo(QPointF(x + s * 0.9, y + s * 0.1), QPointF(x + s * 0.6, y + s * 0.9), QPointF(x, y + s * 0.9))
            path.cubicTo(QPointF(x - s * 0.6, y + s * 0.9), QPointF(x - s * 0.9, y + s * 0.1), QPointF(x, y - s))
            painter.drawPath(path)
            painter.setPen(Qt.NoPen)
        elif k == "puff":
            t = p["t"] / p["life"]
            r = p["s"] * (1 + 1.4 * t)
            cloud = QPainterPath()
            cloud.addEllipse(QPointF(x, y), r, r)
            cloud.addEllipse(QPointF(x - r * 0.7, y + r * 0.25), r * 0.7, r * 0.7)
            cloud.addEllipse(QPointF(x + r * 0.7, y + r * 0.25), r * 0.7, r * 0.7)
            _bw(painter, 0.85 * (1 - t), body_color, 1.1)
            painter.drawPath(cloud.simplified())
            painter.setPen(Qt.NoPen)
        elif k == "snack":
            painter.save()
            painter.translate(x, y)
            painter.rotate(p["t"] * 400)
            _bw(painter, min(1.0, (1 - p["t"] / p["life"]) * 3), body_color)
            painter.drawPath(star_path(p["s"] * (1 - 0.5 * p["t"] / p["life"])))
            painter.restore()
            painter.setPen(Qt.NoPen)
        elif k == "pop":
            _bw(painter, a, body_color, 1.0)
            painter.drawEllipse(QPointF(x, y), p["s"], p["s"])
            painter.setPen(Qt.NoPen)
        elif k == "q":
            size = p["s"] * (0.8 + 0.3 * min(1.0, p["t"] * 4))
            _outlined_text(painter, x, y, "?", size, body_color, a)
        elif k == "gift":
            painter.save()
            painter.translate(x + math.sin(p["t"] * 2.5) * R * 0.08, y)
            pulse = 1.0 + 0.12 * math.sin(p["t"] * 7 + p["ph"])
            grow = min(1.0, p["t"] / 0.35)
            g = QColor(255, 255, 255)
            g.setAlphaF(0.22 * a)
            painter.setPen(Qt.NoPen)
            painter.setBrush(g)
            painter.drawEllipse(QPointF(0, 0), p["s"] * 1.5 * grow, p["s"] * 1.5 * grow)
            painter.rotate(math.sin(p["t"] * 2) * 15)
            _bw(painter, a, body_color, 1.4)
            painter.drawPath(star_path(p["s"] * pulse * grow))
            painter.restore()
            painter.setPen(Qt.NoPen)
        elif k == "spark":
            _bw(painter, a, body_color, 1.0)
            painter.drawEllipse(QPointF(x, y), p["s"] * 1.2, p["s"] * 1.2)
            painter.setPen(Qt.NoPen)
        elif k == "snow":
            c = QColor(250, 250, 252)
            c.setAlphaF(0.9 * min(1.0, (p["life"] - p["t"]) / 0.8))
            painter.setPen(QPen(QColor(40, 40, 46, int(120 * c.alphaF())), 0.8))
            painter.setBrush(c)
            painter.drawEllipse(QPointF(x, y), p["s"], p["s"])
            painter.setPen(Qt.NoPen)
        elif k == "fw":
            q = p["t"] / p["life"]
            c = QColor(255, 255, 255)
            c.setAlphaF(max(0.0, 1.0 - q) ** 0.7)
            painter.setPen(QPen(QColor(20, 20, 24, int(150 * c.alphaF())), 0.8))
            painter.setBrush(c)
            painter.drawEllipse(QPointF(x, y), p["s"] * (1.2 - 0.6 * q), p["s"] * (1.2 - 0.6 * q))
            painter.setPen(Qt.NoPen)

    # globito con lo que necesita (estrellita = hambre, luna = sueño)
    want = fx.get("want")
    if want:
        wt = fx.get("want_t", 0.0)
        a = min(1.0, wt / 0.4, (6.0 - wt) / 0.25 if wt > 5.75 else 1.0)
        bx, by = -R * 1.0, -R * 1.3 + math.sin(wt * 3) * R * 0.04
        painter.save()
        painter.setOpacity(painter.opacity() * max(0.0, a))
        painter.setBrush(QColor(250, 250, 252, 240))
        painter.setPen(QPen(QColor(0, 0, 0, 60), 1))
        painter.drawEllipse(QPointF(bx, by), R * 0.42, R * 0.42)
        painter.drawEllipse(QPointF(bx + R * 0.32, by + R * 0.42), R * 0.09, R * 0.09)
        painter.drawEllipse(QPointF(bx + R * 0.5, by + R * 0.6), R * 0.05, R * 0.05)
        painter.setPen(Qt.NoPen)
        painter.save()
        painter.translate(bx, by)
        painter.setBrush(body_color)                 # icono negro dentro del globito blanco
        if want == "hunger":
            painter.drawPath(star_path(R * 0.26))
        else:
            painter.drawPath(_moon_path(R * 0.22))
        painter.restore()
        painter.restore()
    painter.restore()


def draw_disk(painter, fx, cx, cy, R, front):
    """Disco de agujero negro: puntitos girando en una elipse inclinada (mitad atras, mitad adelante)."""
    if not fx or fx.get("disk", 0.0) < 0.02:
        return
    d = fx["disk"]
    ph = fx["disk_phase"]
    painter.save()
    painter.translate(cx, cy)
    painter.rotate(-14)
    painter.setPen(Qt.NoPen)
    n = 22
    rx, ry = R * (1.25 + 0.35 * d), R * (0.3 + 0.08 * d)
    for i in range(n):
        a = ph + 2 * math.pi * i / n
        sy = math.sin(a)
        if (sy > 0) != front:
            continue
        x, y = math.cos(a) * rx, sy * ry
        depth = 0.55 + 0.45 * sy                 # mas grande y brillante adelante
        r = R * (0.035 + 0.035 * depth) * (0.6 + 0.4 * d)
        _bw(painter, min(1.0, d * (0.35 + 0.65 * depth)), QColor(16, 16, 18), 1.0)   # puntitos negros con borde blanco
        painter.drawEllipse(QPointF(x, y), r, r)
        painter.setPen(Qt.NoPen)
    painter.restore()


# ====================================================================== orbita
def swallow_plan(n):
    """Tiempos de la broma (segundos desde que empieza), para n planetas."""
    pull0 = 0.55                                  # abre la boca y empiezan a volar hacia ella
    pull_each, pull_dur = 0.17, 0.42
    pull_end = pull0 + pull_each * max(0, n - 1) + pull_dur
    chomp = pull_end + 0.02                       # cierra: mordisco
    chew_end = chomp + 1.0                        # mastica con los cachetes inflados
    spit_each, spit_dur = 0.26, 0.6
    spits = [chew_end + 0.15 + spit_each * i for i in range(n)]
    end = (spits[-1] if spits else chew_end) + spit_dur + 0.7
    return {"pull0": pull0, "pull_each": pull_each, "pull_dur": pull_dur, "pull_end": pull_end,
            "chomp": chomp, "chew_end": chew_end, "spits": spits, "spit_dur": spit_dur, "end": end}


def _swallow_state(t, i, n):
    """Para el planeta i: ("orbit", 0) normal, ("pull", k) volando a la boca, ("in", 0) adentro,
    ("spit", k) saliendo disparado."""
    if t is None or t < 0:
        return "orbit", 0.0
    pl = swallow_plan(n)
    s0 = pl["pull0"] + pl["pull_each"] * i
    if t < s0:
        return "orbit", 0.0
    if t < s0 + pl["pull_dur"]:
        return "pull", (t - s0) / pl["pull_dur"]
    sp = pl["spits"][i]
    if t < sp:
        return "in", 0.0
    if t < sp + pl["spit_dur"]:
        return "spit", (t - sp) / pl["spit_dur"]
    return "orbit", 0.0


def _back_out(k, c=1.7):
    k = max(0.0, min(1.0, k))
    return 1 + (c + 1) * (k - 1) ** 3 + c * (k - 1) ** 2


def draw_orbit(painter, orbit, cx, cy, R, front):
    """Planetas de Holi, cada uno en su propia orbita inclinada. Los de adentro giran mas rapido
    (Kepler: velocidad angular ~ r^-1.5). Estilo plano como Holi: color solido y borde suave.
    Se llama dos veces: front=False antes del cuerpo (lo que pasa por detras) y front=True despues."""
    if not orbit:
        return
    planets = orbit.get("planets") or []
    if not planets:
        return
    t = orbit.get("phase", 0.0)
    pop = orbit.get("new", 0.0)                  # recien crecio: se infla un momento
    align = orbit.get("align", 0.0)              # 0..1: los planetas se alinean y brillan
    common = 0.45                                # angulo de la alineacion (adelante, a la derecha)
    painter.save()
    painter.translate(cx, cy)
    painter.rotate(-12)
    edge = QPen(QColor(255, 255, 255, C.RIM_ALPHA + 8), 1.0)
    edge.setCosmetic(True)
    last = len(planets) - 1
    moon_new = orbit.get("moon_new", 0.0)        # recien gano su luna: aparece con un rebote
    for i, pl in enumerate(planets):
        col, size = pl[0], pl[1]
        has_moon = len(pl) > 2 and pl[2]
        r_orb = C.ORBIT_FIRST + C.ORBIT_GAP * i
        omega = C.ORBIT_SPEED * (C.ORBIT_FIRST / r_orb) ** 1.5
        a = t * omega + i * 2.39                 # angulo inicial distinto para cada uno
        if align > 0:
            d = (common - a + math.pi) % (2 * math.pi) - math.pi
            a += d * align
        phase, kk = _swallow_state(orbit.get("swallow", -1.0), i, len(planets))
        if phase == "in":
            continue                             # esta dentro de Holi (en sus cachetes)
        sy = math.sin(a)
        x, y = math.cos(a) * R * r_orb, sy * R * r_orb * 0.28
        r = R * size * (0.9 + 0.1 * sy)          # un poco mas chico cuando pasa por detras
        trail = None
        if phase in ("pull", "spit"):
            # la boca, en las coordenadas de la orbita (que esta inclinada -12 grados)
            mo = orbit.get("mouth", (0.0, 0.38))
            mp = QTransform().rotate(12).map(QPointF(mo[0] * R, mo[1] * R))
            if phase == "pull":                  # vuela hacia la boca acelerando y se achica al entrar
                e = kk * kk
                nx, ny = x + (mp.x() - x) * e, y + (mp.y() - y) * e
                r *= 1.0 - 0.7 * e ** 3
            else:                                # sale disparado de la boca y vuelve a su orbita con rebote
                e = _back_out(kk)
                nx, ny = mp.x() + (x - mp.x()) * e, mp.y() + (y - mp.y()) * e
                r *= 0.45 + 0.55 * min(1.0, kk * 2.2)
            trail = (x if phase == "pull" else mp.x(), y if phase == "pull" else mp.y())
            x, y = nx, ny
            if not front:                        # en transito siempre va por delante de Holi
                continue
        elif (sy > 0) != front:
            continue
        k = (orbit.get("appear", 99.0) - 0.5 - 0.25 * i) / 0.7     # al abrir: aparecen uno por uno
        if k <= 0:
            continue
        if k < 1:
            k = 1 - (1 - k) ** 3
            r *= k * (1.0 + 0.25 * math.sin(k * math.pi))          # crecen con un pequeno rebote
        if i == last and pop > 0:
            r *= 1.0 + 0.35 * math.sin(min(1.0, pop / 2.5) * math.pi)
        beat = orbit.get("pulse", 0.0)
        if beat > 0:
            r *= 1.0 + 0.28 * beat * beat
        if trail is not None:                    # estela del movimiento
            dxt, dyt = trail[0] - x, trail[1] - y
            dl = math.hypot(dxt, dyt)
            if dl > r * 1.5:
                ux, uy = dxt / dl, dyt / dl
                for j in range(3):
                    tc = QColor(col)
                    tc.setAlphaF(0.32 - 0.09 * j)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(tc)
                    off = r * 1.1 * (j + 1)
                    painter.drawEllipse(QPointF(x + ux * off, y + uy * off), r * (0.8 - 0.18 * j), r * (0.8 - 0.18 * j))
        if align > 0.02:
            glow = QColor(col)
            glow.setAlphaF(0.35 * align)
            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(x, y), r * 2.3, r * 2.3)
        moon = None
        if has_moon and phase == "orbit":        # luna: gira rapido alrededor de su planeta, en una orbita plana
            ma = t * 2.6 + i * 1.7
            mr = max(1.6, r * 0.45)
            if has_moon == "new" and moon_new > 0:
                q = 1.0 - moon_new / 2.0
                mr *= max(0.0, q) * (1.0 + 0.4 * math.sin(max(0.0, q) * math.pi))
            moon = (x + math.cos(ma) * (r * 1.4 + 4), y + math.sin(ma) * (r * 1.4 + 4) * 0.35, mr, math.sin(ma) > 0)
        moon_col = QColor(214, 215, 222)
        if moon and not moon[3] and moon[2] > 0.2:    # luna por detras del planeta
            painter.setPen(edge)
            painter.setBrush(moon_col)
            painter.drawEllipse(QPointF(moon[0], moon[1]), moon[2], moon[2])
        painter.setPen(edge)
        painter.setBrush(QColor(col))
        painter.drawEllipse(QPointF(x, y), r, r)
        if moon and moon[3] and moon[2] > 0.2:
            painter.setPen(edge)
            painter.setBrush(moon_col)
            painter.drawEllipse(QPointF(moon[0], moon[1]), moon[2], moon[2])
        if i == 0 and orbit.get("xmas") and phase == "orbit":    # diciembre: arbolito con su estrella
            painter.save()
            painter.translate(x, y - r * 1.55)
            painter.rotate(12 + math.sin(t * 2.0) * 8)
            _bw(painter, 1.0, QColor(16, 16, 18), 1.0)
            painter.drawPath(star_path(max(2.6, r * 0.75)))
            painter.restore()
            painter.setPen(edge)
    painter.restore()


def draw_food(painter, food, cx, cy, R):
    """Estrellita de comida al lado de Holi cuando tiene hambre: arrastrala a su boca."""
    if not food:
        return
    fx_, fy, t, drag = food
    grow = min(1.0, t / 0.4)
    s = R * 0.3 * grow * (1.15 if drag else 1.0 + 0.08 * math.sin(t * 5))
    if s < 0.5:
        return
    painter.save()
    painter.translate(cx + fx_, cy + fy + (0 if drag else math.sin(t * 2.2) * R * 0.06))
    g = QColor(255, 255, 255)
    g.setAlphaF(0.22 + 0.1 * math.sin(t * 4))
    painter.setPen(Qt.NoPen)
    painter.setBrush(g)
    painter.drawEllipse(QPointF(0, 0), s * 1.6, s * 1.6)
    painter.rotate(t * (160 if drag else 25))
    _bw(painter, 1.0, QColor(16, 16, 18), 1.4)
    painter.drawPath(star_path(s))
    painter.restore()


# ====================================================================== accesorios
def hat_for(today=None):
    d = today or dt.date.today()
    if (d.month == 12 and d.day == 31) or (d.month == 1 and d.day == 1):
        return "party"
    if d.month == 12:
        return "santa"
    if d.month == 9 and 14 <= d.day <= 20:
        return "flag"
    if d.month == 10 and d.day == 31:
        return "witch"
    return None


def draw_hat(painter, hat, R, t):
    """Se dibuja dentro de la transformacion del cuerpo (sigue saltos, inclinacion y aplastadas).
    En blanco y negro como Holi: blanco con detalles negros, o negro con borde blanco."""
    if not hat:
        return
    W = QColor(244, 244, 247)
    K = QColor(16, 16, 18)
    edge = QPen(W, max(1.0, R * 0.045))
    edge.setJoinStyle(Qt.RoundJoin)
    painter.save()
    painter.setPen(Qt.NoPen)
    if hat == "santa":
        painter.translate(R * 0.08, -R * 0.82)
        painter.rotate(14)
        sway = math.sin(t * 1.6) * R * 0.05
        path = QPainterPath(QPointF(-R * 0.62, 0))
        path.cubicTo(QPointF(-R * 0.45, -R * 0.7), QPointF(R * 0.1, -R * 0.95), QPointF(R * 0.55 + sway, -R * 0.62))
        path.cubicTo(QPointF(R * 0.35, -R * 0.45), QPointF(R * 0.45, -R * 0.2), QPointF(R * 0.62, 0))
        path.closeSubpath()
        painter.setBrush(W)
        painter.drawPath(path)
        painter.setPen(edge)
        painter.setBrush(K)
        painter.drawRoundedRect(QRectF(-R * 0.7, -R * 0.13, R * 1.4, R * 0.26), R * 0.13, R * 0.13)
        painter.drawEllipse(QPointF(R * 0.58 + sway, -R * 0.6), R * 0.14, R * 0.14)
    elif hat == "party":
        painter.translate(-R * 0.15, -R * 0.86)
        painter.rotate(-12)
        path = QPainterPath(QPointF(-R * 0.36, 0))
        path.lineTo(QPointF(0, -R * 0.85))
        path.lineTo(QPointF(R * 0.36, 0))
        path.closeSubpath()
        painter.setBrush(W)
        painter.drawPath(path)
        painter.setClipPath(path)
        painter.setBrush(K)
        for i in range(3):
            y = -R * (0.15 + 0.25 * i)
            painter.drawRect(QRectF(-R * 0.5, y - R * 0.05, R, R * 0.09))
        painter.setClipping(False)
        painter.setPen(edge)
        painter.drawEllipse(QPointF(0, -R * 0.88), R * 0.1, R * 0.1)
    elif hat == "flag":                          # banderita chilena en blanco y negro
        painter.translate(R * 0.45, -R * 0.78)
        painter.rotate(10 + math.sin(t * 2.0) * 3)
        painter.setPen(QPen(W, max(1.0, R * 0.04)))
        painter.drawLine(QPointF(0, 0), QPointF(0, -R * 0.85))
        w, h = R * 0.62, R * 0.4
        top = -R * 0.85
        painter.setPen(edge)
        painter.setBrush(K)
        painter.drawRect(QRectF(0, top, w, h))
        painter.setPen(Qt.NoPen)
        painter.setBrush(W)
        painter.drawRect(QRectF(h / 2, top, w - h / 2, h / 2))
        painter.save()
        painter.translate(h / 4, top + h / 4)
        painter.drawPath(star_path(R * 0.075))
        painter.restore()
    elif hat == "witch":
        painter.translate(0, -R * 0.8)
        painter.rotate(-8)
        brim = QPainterPath()
        brim.addEllipse(QPointF(0, 0), R * 0.8, R * 0.16)
        cone = QPainterPath(QPointF(-R * 0.42, 0))
        cone.cubicTo(QPointF(-R * 0.25, -R * 0.6), QPointF(R * 0.05, -R * 0.9), QPointF(R * 0.45, -R * 1.0))
        cone.cubicTo(QPointF(R * 0.15, -R * 0.7), QPointF(R * 0.3, -R * 0.3), QPointF(R * 0.42, 0))
        cone.closeSubpath()
        painter.setPen(edge)
        painter.setBrush(K)
        painter.drawPath(brim.united(cone))
        painter.setPen(Qt.NoPen)
        painter.setBrush(W)
        painter.drawRect(QRectF(-R * 0.4, -R * 0.16, R * 0.8, R * 0.1))
    painter.restore()
