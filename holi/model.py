"""
Estado y comportamiento de Holi. No depende de Qt.

Antes de cada update() el controlador deja en el modelo lo que sabe del mundo:
  fg          (hwnd, (x, y, w, h)) ventana activa donde podria posarse, o None
  perch_rect  rectangulo actual de la ventana donde esta posado (o hacia la que va)
  hour        hora local (float)
Coordenadas: pixeles logicos globales del escritorio.
"""
import math
import random

from . import config as C
from .physics import Spring, Spring2, approach, clamp

from .fx import Particles, swallow_plan

EXPRESSIONS = ("glare", "sad", "serious", "suspicious", "curious", "impact", "excited", "proud", "angry", "love",
               "puzzled")


class BlobModel:
    IDLE, WANDER, DRAG, THROWN, PERCH, FALL = "idle", "wander", "drag", "thrown", "perch", "fall"

    def __init__(self, radius, x, y):
        self.R = float(radius)
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.t = 0.0

        self.mode = self.IDLE
        self.decide_in = random.uniform(2.0, 5.0)
        self.target = None
        self.speed = 60.0

        # deformacion
        self.stretch = Spring2(k=170.0, c=8.5)
        self.squash = Spring(0.0, k=210.0, c=9.0)
        self.lean = Spring(0.0, k=70.0, c=13.0)
        self.hop = Spring(0.0, k=170.0, c=11.0)       # saltitos en el lugar (px)
        self.wobble = 0.012
        self.bob_amp = 1.0

        # cara
        self.yaw = Spring(C.FACE_YAW, k=260.0, c=30.0)
        self.pitch = Spring(C.FACE_PITCH, k=260.0, c=30.0)
        self.glance = (C.FACE_YAW, C.FACE_PITCH)
        self.glance_in = random.uniform(2.5, 5.0)
        self.blink_in = random.uniform(1.5, 4.0)
        self.blink_t = -1.0
        self.double_blink = False
        self.happy = Spring(0.0, k=90.0, c=13.0)
        self.happy_time = 0.0
        self.wide = Spring(0.0, k=120.0, c=14.0)
        self.sleepy = 0.0
        self.since_interaction = 0.0
        self.expr = {k: 0.0 for k in EXPRESSIONS}
        self.expr_hold = {k: 0.0 for k in EXPRESSIONS}
        self.wink_t = -1.0
        self.wink_side = 1
        self.clicks = []
        self.headshake_t = 0.0

        # cursor
        self.cursor_prev = None
        self.cursor_still = 0.0
        self.curious_cd = 0.0
        self.startle_cd = 0.0
        self.near_still = 0.0

        # arrastre
        self.pressing = False
        self.press_pos = (0.0, 0.0)
        self.grab = (0.0, 0.0)
        self.drag_target = (self.x, self.y)

        # no estorbar / caricias / mareo
        self.alpha = 1.0
        self.hover_t = 0.0
        self.pet = 0.0
        self.pet_time = 0.0
        self.make_way_cd = 0.0
        self.dizzy_t = 0.0
        self.shake = 0.0
        self.prev_vang = None
        self.micro = (0.0, 0.0)
        self.micro_in = 0.5

        # actividad del PC y hora
        self.key_times = []
        self.typing = 0.0
        self.asleep = False
        self.hour = 12.0
        self.night_cd = 20.0

        # mundo
        self.fg = None
        self.perch_rect = None
        self.perch = None             # {"hwnd", "off"}
        self.perch_goal = None        # hwnd hacia el que vuela
        self.perch_time = 0.0
        self.perch_cd = 20.0
        self.celebrate_t = 0.0
        self.celebrate_bounce = 0.0
        self.sfx = []                 # ruiditos pendientes (los reproduce el controlador)
        self.anchor = None            # (x, y) si esta fijo en una esquina
        self.dropped = None           # (x, y) donde lo soltaste estando fijo (lo usa el controlador)
        self.look_at_pt = None        # punto al que mirar un rato (ventana nueva, etc.)
        self.look_at_t = 0.0
        self.typing_time = 0.0
        self.mood_in = 6.0            # cada cuanto cambia de animo cuando esta fijo
        self.sleepy_hold = 0.0
        self.activity = 0.0           # cuanto estas moviendo el mouse (0..1)
        self.temper = "contento"      # sentimiento del corazon (lo pone el controlador)
        self.heart_energy = None      # 0..1 energia del corazon (None = segun la hora)
        self.events = []              # cosas que le pasaron (las consume el controlador)
        self.fx = Particles()         # zzz, corazones, sudor, nubecita, globito, disco de agujero negro
        self.hat = None               # accesorio segun la fecha (lo pone el controlador)
        self.gulp_t = 0.0
        # mascota virtual (los pone el controlador)
        self.napping = False          # siesta pedida: no despierta con el mouse ni el teclado
        self.need_sad = 0.0           # 0..1 cara triste permanente por una necesidad sin atender
        self.need_angry = 0.0         # 0..1 cara enojada permanente
        self.need_target = (0.0, 0.0)
        self.orbit = None             # {"planets": [(color, tamano)], "new": seg} planetas que lo orbitan
        self.orbit_phase = random.uniform(0, 6.28)
        self.unlocks = set()          # cosas que aprendio con la confianza (las pone el controlador)
        self.cuddle_cd = 0.0
        self.align_t = 0.0            # planetas alineados (segundos restantes)
        self.dance_t = 0.0            # bailecito (segundos restantes)
        self.boot_t = 0.0             # segundos desde que se abrio (planetas aparecen uno por uno)
        self.spin_t = 0.0             # segundos desde el ultimo "saludo" girando los planetas
        self.swallow_t = -1.0         # broma: se traga los planetas y los escupe (-1 = no)
        self.swallow_cd = 300.0
        self.puff = 0.0               # cachetes inflados mientras tiene los planetas adentro
        # boca (solo aparece en los gestos): forma y cuanto esta abierta
        self.mouth_shape = None
        self.mouth_open = 0.0
        self.mouth_pos = (0.0, 0.40)  # donde queda la boca, relativa a Holi (en radios)
        self.yawn_t = 0.0             # bostezo: entrecierra los ojos
        self.laugh_t = 0.0            # risa: ojitos felices

    # ================================================================== API
    def set_radius(self, r):
        self.R = float(r)

    def feel(self, name, secs):
        if self.expr_hold[name] <= 0 and self.expr[name] < 0.3:
            snd = {"sad": "aww", "love": "love", "angry": "grr"}.get(name)
            if snd:
                self.sfx.append(snd)
        self.expr_hold[name] = max(self.expr_hold[name], secs)

    def glance_at(self, x, y, secs=1.4):
        """Mira un punto un momento (por ejemplo la ventana que acabas de abrir)."""
        self.look_at_pt = (x, y)
        self.look_at_t = secs
        if not self.asleep and self.mode in (self.IDLE, self.PERCH):
            self.hop.impulse(-60)
            self.feel("curious", 0.8)

    def press(self, gx, gy):
        self.pressing = True
        self.press_pos = (gx, gy)
        self.grab = (gx - self.x, gy - self.y)
        self.drag_target = (self.x, self.y)
        self._touch()

    def move_pointer(self, gx, gy):
        if not self.pressing:
            return
        if self.mode != self.DRAG and math.hypot(gx - self.press_pos[0], gy - self.press_pos[1]) > 4:
            self.mode = self.DRAG
            self.target = None
            self.perch = None
            self.perch_goal = None
            self.wide.target = 0.35
        if self.mode == self.DRAG:
            self.drag_target = (gx - self.grab[0], gy - self.grab[1])

    def release(self):
        """Devuelve "click" o "drag" segun lo que paso."""
        if not self.pressing:
            return None
        self.pressing = False
        if self.mode == self.DRAG:
            sp = math.hypot(self.vx, self.vy)
            if sp > 1100:
                self.vx, self.vy = self.vx / sp * 1100, self.vy / sp * 1100
            self.mode = self.THROWN
            self.wide.target = 0.0
            self.wobble = max(self.wobble, 0.045)
            self.squash.impulse(4.5)
            if math.hypot(self.vx, self.vy) > 400:
                self.sfx.append("wee")
                self.events.append("thrown")
            if self.anchor is not None:
                self.dropped = (self.x, self.y)
            return "drag"
        self.click()
        return "click"

    def click(self):
        self._touch()
        if self.asleep and self.napping:      # siesta: se acomoda y sigue durmiendo
            self.squash.impulse(3.0)
            self.wobble = max(self.wobble, 0.02)
            return
        if self.asleep:
            self._wake()
        self.squash.impulse(7.0)
        self.wobble = max(self.wobble, 0.035)
        self.clicks = [c for c in self.clicks if self.t - c < 2.0] + [self.t]
        if len(self.clicks) >= 6:              # muchos clics seguidos: se enoja
            self.feel("angry", 2.5)
            self.events.append("annoyed")
            self.clicks = []
            self.hop.impulse(-60)
            return
        self.events.append("click")
        self.happy.target = 1.0
        self.happy_time = 1.3
        if random.random() < 0.3:              # a veces guina un ojo
            self.wink_t = 0.0
            self.wink_side = random.choice((-1, 1))
            self.sfx.append("giggle")
        else:
            self.sfx.append("boop")
        if self.mode in (self.IDLE, self.WANDER):
            self.hop.impulse(-140)

    def bring_to(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.mode = self.IDLE
        self.perch = self.perch_goal = None
        self.asleep = self.napping
        self.decide_in = random.uniform(3.0, 6.0)
        self.squash.impulse(5.0)
        self.wobble = 0.045

    def gulp(self):
        """Se trago la comida: glup, se infla, gira el disco y queda feliz."""
        self.gulp_t = 1.3
        self.squash.impulse(-9.0)
        self.wide.impulse(3.0)
        self.hop.impulse(-120)
        self.happy.target = 1.0
        self.happy_time = 1.6
        self.fx.burst(self.R, 12)
        self.sfx.append("gulp")

    def celebrate(self):
        self.sfx.append("tada")
        self.celebrate_t = 2.4
        self.celebrate_bounce = 0.0
        self.happy.target = 1.0
        self.happy_time = 2.6
        self.feel("proud", 2.6)

    # ------------------------------------------------------------ mascota virtual
    def eat(self):
        """Le diste comida: se la traga feliz."""
        if self.asleep and not self.napping:
            self._wake()
        self.gulp()
        self.feel("love", 1.6)
        self.happy_time = 2.2

    def refuse(self):
        """No necesita eso ahora: niega con el cuerpo."""
        if self.asleep and not self.napping:
            self._wake()
        self.headshake_t = 1.2
        self.feel("suspicious", 1.2)

    def start_nap(self):
        self.napping = True
        self.asleep = True
        self.perch = self.perch_goal = None
        if self.mode not in (self.DRAG, self.THROWN, self.FALL):
            self.mode = self.IDLE
        self.target = None
        self.squash.impulse(4.0)
        self.sfx.append("yawn")

    def end_nap(self):
        self.napping = False
        if self.asleep:
            self._wake()
        self.squash.impulse(-6.0)
        self.happy.target = 1.0
        self.happy_time = 1.8
        self.hop.impulse(-150)

    # ------------------------------------------------------------ desbloqueos de confianza
    def greet(self):
        """Volviste: saltito, ojos felices, un ruidito y los planetas giran saludando."""
        if self.asleep and not self.napping:
            self._wake()
        if self.asleep:
            return
        self.spin_planets()
        self.hop.impulse(-220)
        self.squash.impulse(-6.0)
        self.happy.target = 1.0
        self.happy_time = 2.0
        self.feel("love", 1.2)
        self.sfx.append("love")

    def _cuddle(self):
        """Cursor quieto cerca: se acerca, se pega a el y ronronea."""
        cx, cy = self.cursor_prev
        side = 1 if self.x > cx else -1
        self.perch = self.perch_goal = None
        self._go((cx + side * self.R * 1.55, cy + self.R * 0.2), 90.0)
        self.feel("love", 2.4)
        self.sleepy_hold = 2.0
        self.sfx.append("purr")
        self.near_still = -10.0
        self.cuddle_cd = C.CUDDLE_COOLDOWN

    def spin_planets(self):
        """Saludo: los planetas giran rapido unos segundos."""
        self.spin_t = 0.0

    def can_swallow(self):
        return (self.swallow_t < 0 and self.swallow_cd <= 0 and self.align_t <= 0 and not self.asleep
                and bool(self.orbit and self.orbit.get("planets")))

    def swallow_planets(self):
        """Broma: se traga sus planetas en espiral, se queda inflado y los escupe uno por uno."""
        if self.swallow_t >= 0 or not (self.orbit and self.orbit.get("planets")):
            return
        self.swallow_t = 0.0
        self.wink_t = 0.0
        self.wink_side = 1
        self.sfx.append("giggle")
        self.wide.impulse(4.0)

    def _swallow_step(self, dt):
        self.swallow_cd = max(0.0, self.swallow_cd - dt)
        if self.swallow_t < 0:
            self.puff = max(0.0, self.puff - dt * 3)
            return
        n = len(self.orbit.get("planets") or []) if self.orbit else 0
        pl = swallow_plan(n)
        t0 = self.swallow_t
        t1 = t0 + dt
        self.swallow_t = t1

        def at(x):
            return t0 < x <= t1
        for i in range(n):                       # cada planeta que entra: un tironcito
            if at(pl["pull0"] + pl["pull_each"] * i + pl["pull_dur"] * 0.9):
                self.squash.impulse(-4.0)
                self.hop.impulse(-30)
        if at(pl["chomp"]):                        # ñam: cierra la boca
            self.squash.impulse(9.0)
            self.hop.impulse(-90)
            self.sfx.append("gulp")
        if pl["chomp"] <= t1 <= pl["chew_end"] + 0.05:   # inflado, mastica con cara de travieso
            self.puff = min(1.0, self.puff + dt * 7)
            self.happy.target = 1.0
            self.happy_time = 0.3
            ph = (t1 - pl["chomp"]) * 7.0
            if int(ph) != int((t1 - dt - pl["chomp"]) * 7.0):
                self.squash.impulse(2.5)
        for i, sp in enumerate(pl["spits"]):       # los escupe: boca abierta, ¡pop!, se echa para atras
            if at(sp):
                self.sfx.append("pip")
                self.hop.impulse(-95)
                self.squash.impulse(-6.0)
                self.wide.impulse(3.0)
                for a in range(8):
                    self.fx.emit("pop", self.R, a=2 * math.pi * a / 8 + random.uniform(-0.3, 0.3),
                                 at=self.mouth_pos)
                left = n - 1 - i
                self.puff = max(0.0, left / max(1, n))
        if pl["spits"] and t1 > pl["spits"][-1]:
            self.puff = max(0.0, self.puff - dt * 4)
        if at(pl["end"] - 0.65):
            self.sfx.append("giggle")
            self.happy.target = 1.0
            self.happy_time = 1.2
        if t1 >= pl["end"]:
            self.swallow_t = -1.0
            self.swallow_cd = random.uniform(900.0, 1800.0)

    def _swallow_mouth(self):
        """Boca durante la broma."""
        n = len(self.orbit.get("planets") or []) if self.orbit else 0
        pl = swallow_plan(n)
        t = self.swallow_t
        if t < pl["pull0"] - 0.2:
            return "smile", 0.45                   # sonrisa traviesa
        if t < pl["chomp"]:
            return "o", 1.0                        # boca bien abierta
        if t < pl["chew_end"]:
            return "chew", 1.0
        for sp in pl["spits"]:
            if sp - 0.08 <= t <= sp + 0.14:
                return "o", 0.8                    # abre para escupir
        if pl["spits"] and t < pl["spits"][-1] + 0.2:
            return "chew", 1.0
        return "smile", 1.0                        # se rie

    def give_gift(self):
        """Te trae una estrellita de regalo."""
        if self.asleep:
            return
        self.fx.emit("gift", self.R)
        self.hop.impulse(-160)
        self.happy.target = 1.0
        self.happy_time = 1.8
        self.sfx.append("giggle")

    def align(self):
        self.align_t = C.ALIGN_SECONDS
        self.happy.target = 1.0
        self.happy_time = 2.5
        self.sfx.append("tada")

    def reclaim(self, kind, stage):
        """Te recuerda lo que necesita (como maximo cada RECLAIM_EVERY minutos)."""
        if self.asleep and not self.napping:
            self._wake()
        self.fx.want = kind
        self.fx.want_t = 6.0
        self.hop.impulse(-110)
        if stage >= 3:
            self.feel("angry", 2.5)
        else:
            self.feel("sad", 2.5)
        if kind == "sleep":
            self.sleepy_hold = 4.0

    def suggest_break(self, cx, cy):
        """Pausa: se despereza mirandote, como invitandote a pararte."""
        if self.asleep and not self.napping:
            self._wake()
        self.glance_at(cx, cy, 2.5)
        self.squash.impulse(-11.0)
        self.hop.impulse(-90)
        self.sleepy_hold = 1.4
        self.happy.target = 0.6
        self.happy_time = 1.6
        self.sfx.append("yawn")

    # ------------------------------------------------------------ boca
    def _mouth(self, dt):
        # los ruiditos dicen que cara poner
        for s in self.sfx:
            if s == "giggle":
                self.laugh_t = max(self.laugh_t, 0.8)
            elif s == "yawn":
                self.yawn_t = max(self.yawn_t, 1.4)
            elif s in ("love", "purr", "tada"):
                self.laugh_t = max(self.laugh_t, 0.9)
        self.yawn_t = max(0.0, self.yawn_t - dt)
        self.laugh_t = max(0.0, self.laugh_t - dt)
        if self.laugh_t > 0 and self.swallow_t < 0:
            self.happy.target = 1.0                # se rie con ojitos felices
            self.happy_time = max(self.happy_time, 0.2)
        if self.swallow_t >= 0:
            shape, target = self._swallow_mouth()
        else:
            shape, target = None, 0.0              # la boca solo aparece en la broma
        # cambia de forma suave: primero cierra la anterior
        if shape != self.mouth_shape and self.mouth_open > 0.05:
            self.mouth_open = approach(self.mouth_open, 0.0, 14.0, dt)
        else:
            if shape is not None:
                self.mouth_shape = shape
            self.mouth_open = approach(self.mouth_open, target if shape else 0.0, 12.0, dt)
            if self.mouth_open <= 0.01 and shape is None:
                self.mouth_shape = None

    def _lumps(self):
        """Bultos de los cachetes inflados (con los planetas adentro)."""
        if self.puff <= 0.02:
            return None
        w = math.sin(self.t * 8.0)
        amp = 0.075 * self.puff
        return [(0.45 + 0.18 * w, amp * (1 + 0.25 * w)), (math.pi - 0.45 + 0.18 * w, amp * (1 - 0.25 * w))]

    def is_calm(self):
        return (self.mode == self.IDLE and not self.pressing
                and abs(self.vx) + abs(self.vy) < 5
                and self.stretch.energy() < 0.02 and abs(self.squash.v) < 0.05 and abs(self.hop.v) < 1
                and self.blink_t < 0 and self.happy.x < 0.02 and self.pet < 0.02
                and abs(self.alpha - 1.0) < 0.01 and self.dizzy_t <= 0
                and max(self.expr_hold.values()) <= 0 and not self.fx.busy())

    def energy(self):
        """Animo segun la hora: mas activo en la manana, tranquilo de noche."""
        if not C.S["time_mood"]:
            return 1.0
        if self.heart_energy is not None:
            return 0.5 + 0.8 * self.heart_energy
        h = self.hour
        if 6 <= h < 12:
            return 1.25
        if 12 <= h < 19:
            return 1.0
        if 19 <= h < 23:
            return 0.8
        return 0.55

    # =============================================================== update
    def update(self, dt, cursor, screens, idle=0.0, keys=0):
        dt = clamp(dt, 0.0, 0.05)
        self.t += dt
        self.boot_t += dt
        self.spin_t += dt
        self.since_interaction += dt
        for name in ("curious_cd", "startle_cd", "perch_cd", "night_cd", "make_way_cd"):
            setattr(self, name, max(0.0, getattr(self, name) - dt))

        cx, cy = cursor
        if self.cursor_prev is None:
            self.cursor_prev = cursor
        cspeed = math.hypot(cx - self.cursor_prev[0], cy - self.cursor_prev[1]) / max(dt, 1e-3)
        self.activity = approach(self.activity, 1.0 if cspeed > 60 else 0.0, 1.5, dt)
        if self.anchor is not None and (self.activity > 0.5 or self.typing > 0.5):
            self.since_interaction = 0.0          # fijo: si estas trabajando, no le da sueno
        self.cursor_still = self.cursor_still + dt if cspeed < 5 else 0.0
        self.cursor_prev = cursor
        dx, dy = cx - self.x, cy - self.y
        dist = math.hypot(dx, dy)
        near = dist < C.CURSOR_NEAR and not self.pressing
        if near:
            self._touch(soft=True)

        self._activity(dt, idle, keys)
        self._comfort(dt, dx, dy, dist, cspeed)
        self._behave(dt, dx, dy, dist, cspeed, near, screens)
        self._integrate(dt, screens)
        self._dizzy(dt)
        self._expressions(dt, dist, near)
        self._deform(dt, dx, dy, dist, near)
        self._face(dt, dx, dy, dist, near)
        self.gulp_t = max(0.0, self.gulp_t - dt)
        self._mouth(dt)
        self.fx.update(self, dt)

    # ============================================================ internals
    def _touch(self, soft=False):
        if self.sleepy > 0.5 and not soft:
            self.wide.impulse(3.0)
        self.since_interaction = 0.0

    def _wake(self):
        self.sfx.append("yawn")
        self.events.append("wake")
        self.asleep = False
        self.wide.impulse(7.0)
        self.squash.impulse(-5.0)
        self.wobble = max(self.wobble, 0.03)
        self.since_interaction = 0.0
        self.decide_in = random.uniform(3.0, 6.0)
        if 6 <= self.hour < 11:                 # en la manana despierta estirandose
            self.squash.impulse(-4.0)
            self.happy.target = 0.6
            self.happy_time = 1.0

    def _screen_of(self, screens, x, y):
        for r in screens:
            if r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]:
                return r
        if not screens:
            return (0, 0, 1920, 1080)
        return min(screens, key=lambda r: abs(r[0] + r[2] / 2 - x) + abs(r[1] + r[3] / 2 - y))

    def _floor(self, screens):
        r = self._screen_of(screens, self.x, self.y)
        return r[1] + r[3] - self.R * 1.15

    def _pick_target(self, screens):
        here = self._screen_of(screens, self.x, self.y)
        scr = here if (len(screens) < 2 or random.random() < 0.8) else random.choice(screens)
        m = self.R * 1.6
        for _ in range(12):
            if scr is here:
                ang = random.uniform(0, 2 * math.pi)
                d = random.uniform(*C.WANDER_DISTANCE)
                tx, ty = self.x + math.cos(ang) * d, self.y + math.sin(ang) * d * 0.7
            else:
                tx = random.uniform(scr[0] + m, scr[0] + scr[2] - m)
                ty = random.uniform(scr[1] + m, scr[1] + scr[3] - m)
            if scr[0] + m <= tx <= scr[0] + scr[2] - m and scr[1] + m <= ty <= scr[1] + scr[3] - m:
                return tx, ty
        return scr[0] + scr[2] / 2, scr[1] + scr[3] * 0.7

    def _go(self, target, speed):
        self.target = target
        self.speed = speed
        self.mode = self.WANDER

    # ------------------------------------------------------------ actividad
    def _activity(self, dt, idle, keys):
        now = self.t
        if keys:
            self.key_times.append(now)
            if self.mode in (self.IDLE, self.PERCH) and not self.asleep:
                self.squash.impulse(-0.35)
        self.key_times = [k for k in self.key_times if now - k < 1.5]
        typing = len(self.key_times) / 1.5 >= C.TYPING_RATE
        self.typing = approach(self.typing, 1.0 if typing else 0.0, 3.0 if typing else 0.7, dt)

        sleep_after = C.S["pc_sleep_min"] * 60.0 * (0.6 if self.energy() < 0.6 else 1.0)
        if self.napping:
            self.asleep = True
        elif (not self.asleep and idle > sleep_after and self.mode in (self.IDLE, self.PERCH)
                and not self.pressing):
            self.asleep = True
        elif self.asleep and idle < 1.0:
            self._wake()

        # de madrugada y sigues en el PC: te mira con cara de "anda a dormir"
        late = C.S["time_mood"] and (0 <= self.hour < 5)
        if late and idle < 5 and self.night_cd <= 0 and self.mode in (self.IDLE, self.PERCH, self.WANDER):
            self.feel("glare", 3.5)
            self.headshake_t = 2.0
            self.night_cd = 300.0

        # escribiendo concentrado un buen rato: lo celebra con un saltito
        if self.typing > 0.5:
            self.typing_time += dt
            if self.typing_time > 45.0:
                self.typing_time = 0.0
                self.happy.target = 1.0
                self.happy_time = 1.0
                self.hop.impulse(-90)
        else:
            self.typing_time = max(0.0, self.typing_time - dt * 2)

    def _comfort(self, dt, dx, dy, dist, cspeed):
        over = dist < self.R * 1.15 and not self.pressing and self.mode != self.DRAG
        self.hover_t = self.hover_t + dt if over else 0.0

        petting = over and 40 < cspeed < 900
        self.pet = approach(self.pet, 1.0 if petting else 0.0, 3.0 if petting else 1.2, dt)
        self.pet_time = self.pet_time + dt if petting else max(0.0, self.pet_time - dt * 2)
        if petting:
            self._touch(soft=True)
            self.wobble = max(self.wobble, 0.02)
            if self.pet > 0.6:
                self.sfx.append("purr")
            if self.asleep and not self.napping:
                self._wake()

        parked = over and cspeed < 5 and self.hover_t > 0.4 and self.pet < 0.3
        fade = parked or (over and self.typing > 0.5)
        self.alpha = approach(self.alpha, C.S["fade_alpha"] if fade else 1.0, 6.0, dt)

        if (over and self.make_way_cd <= 0 and self.anchor is None and self.mode in (self.IDLE, self.WANDER, self.PERCH)
                and (self.typing > 0.5 or (cspeed < 5 and self.hover_t > 2.0))):
            ux, uy = (-dx / dist, -dy / dist) if dist > 1 else (0.0, -1.0)
            self.perch = self.perch_goal = None
            self._go((self.x + ux * self.R * 3.4, self.y + uy * self.R * 3.4), 110.0)
            self.make_way_cd = 2.5

    def _dizzy(self, dt):
        if self.mode == self.DRAG:
            if math.hypot(self.vx, self.vy) > 250:
                ang = math.atan2(self.vy, self.vx)
                if self.prev_vang is not None:
                    self.shake += abs((ang - self.prev_vang + math.pi) % (2 * math.pi) - math.pi)
                self.prev_vang = ang
        else:
            self.prev_vang = None
            self.dizzy_t = max(0.0, self.dizzy_t - dt)
        self.shake *= math.exp(-1.2 * dt)
        if self.shake > 7.0:
            self.dizzy_t = 3.0
            self.shake = 0.0

    # ------------------------------------------------------------ conducta
    def _behave(self, dt, dx, dy, dist, cspeed, near, screens):
        if self.mode in (self.DRAG, self.THROWN, self.FALL) or self.asleep:
            return
        spd = C.S["speed"] * math.sqrt(self.energy())

        if self.celebrate_t > 0:
            return

        # fijo en una esquina: vuelve a su lugar y no pasea
        if self.anchor is not None:
            self.perch = self.perch_goal = None
            ax, ay = self.anchor
            if math.hypot(ax - self.x, ay - self.y) > 3:
                if self.mode != self.WANDER or self.target != self.anchor:
                    self._go(self.anchor, 170.0)
            elif self.mode == self.WANDER:
                self.mode = self.IDLE
            self.decide_in = 99
            return

        if self.mode == self.PERCH:
            return

        # susto
        if dist < self.R * 3.6 and cspeed > 1800 and self.startle_cd <= 0:
            nx, ny = (dx / dist, dy / dist) if dist > 1 else (0.0, -1.0)
            self.vx -= nx * 230
            self.vy -= ny * 230
            self.sfx.append("eep")
            self.mode = self.THROWN
            self.wide.impulse(6.0)
            self.squash.impulse(-4.0)
            self.wobble = max(self.wobble, 0.05)
            self.startle_cd = 3.0
            self._touch()
            return

        # curiosidad
        if (near and self.mode == self.IDLE and self.cursor_still > 1.4 and self.curious_cd <= 0
                and dist > self.R * 3.2):
            k = (dist - self.R * 2.6) / dist
            self._go((self.x + dx * k, self.y + dy * k), 48.0)
            self.curious_cd = 14.0
            self.feel("curious", 2.5)
            return

        if self.mode != self.IDLE:
            return
        self.decide_in -= dt
        if self.typing > 0.5 or self.dizzy_t > 0:
            self.decide_in = max(self.decide_in, 2.0)
        if self.decide_in > 0:
            return

        e = self.energy()
        # posarse sobre la ventana activa
        if (C.S["perch"] and self.fg is not None and self.perch_cd <= 0 and not near
                and random.random() < 0.35):
            hwnd, (fx, fy, fw, fh) = self.fg
            ty = fy - self.R * 0.92
            if any(r[0] <= fx + fw / 2 <= r[0] + r[2] and r[1] + self.R * 1.5 <= ty <= r[1] + r[3] for r in screens):
                tx = clamp(self.x, fx + self.R * 1.5, fx + fw - self.R * 1.5)
                self.perch_goal = hwnd
                self._go((tx, ty), 85.0 * spd)
                self.perch_cd = 40.0
                return
        if random.random() < min(0.85, 0.6 * e) and not near:
            self._go(self._pick_target(screens), random.uniform(*C.WANDER_SPEED) * spd *
                     (0.6 if self.sleepy > 0.5 else 1.0))
        else:
            lo, hi = C.IDLE_TIME
            self.decide_in = random.uniform(lo, hi) / e

    # ------------------------------------------------------------ fisica
    def _integrate(self, dt, screens):
        if self.mode == self.DRAG:
            tx, ty = self.drag_target
            k, c = 520.0, 40.0
            self.vx += (-k * (self.x - tx) - c * self.vx) * dt
            self.vy += (-k * (self.y - ty) - c * self.vy) * dt
        elif self.mode == self.PERCH:
            r = self.perch_rect
            if r is None or self.perch is None:
                self.mode = self.FALL               # la ventana se cerro o minimizo: se cae
                self.perch = None
                self.sfx.append("eep")
                self.wide.impulse(6.0)
                self.squash.impulse(-3.0)
                return self._integrate(dt, screens)
            nx = clamp(r[0] + self.perch["off"], r[0] + self.R, r[0] + r[2] - self.R)
            ny = r[1] - self.R * 0.92
            if dt > 0:
                self.vx = clamp((nx - self.x) / dt, -3000, 3000)
                self.vy = clamp((ny - self.y) / dt, -3000, 3000)
            self.x, self.y = nx, ny
            self.perch_time -= dt
            if self.perch_time <= 0:                # se baja de un saltito
                self.perch = None
                self.mode = self.THROWN
                self.vx = random.choice((-1, 1)) * 70.0
                self.vy = -240.0
                self.squash.impulse(-4.0)
            return
        elif self.mode == self.FALL:
            self.vy += C.GRAVITY * dt
            self.vx *= math.exp(-0.6 * dt)
        elif self.mode == self.THROWN:
            f = math.exp(-3.2 * dt)
            self.vx *= f
            self.vy *= f
            if math.hypot(self.vx, self.vy) < 18:
                self.mode = self.IDLE
                self.decide_in = random.uniform(*C.IDLE_TIME)
        elif self.mode == self.WANDER and self.target:
            tx, ty = self.target
            ddx, ddy = tx - self.x, ty - self.y
            d = math.hypot(ddx, ddy)
            if d < 4 and math.hypot(self.vx, self.vy) < 12:
                self.mode = self.IDLE
                self.target = None
                self.decide_in = random.uniform(*C.IDLE_TIME) / self.energy()
                self._arrive()
            else:
                s = self.speed * clamp(d / 110.0, 0.0, 1.0)
                sway = math.sin(self.t * 1.3) * 0.18
                ux, uy = (ddx / d, ddy / d) if d > 1e-3 else (0.0, 0.0)
                wx, wy = (ux - uy * sway) * s, (uy + ux * sway) * s
                self.vx = approach(self.vx, wx, 2.2, dt)
                self.vy = approach(self.vy, wy, 2.2, dt)
        else:
            self.vx = approach(self.vx, 0.0, 3.5, dt)
            self.vy = approach(self.vy, 0.0, 3.5, dt)

        self.x += self.vx * dt
        self.y += self.vy * dt

        if self.mode == self.FALL:
            floor = self._floor(screens)
            if self.y >= floor:
                self.y = floor
                if self.vy > 300:
                    self.sfx.append("bonk")
                if self.vy > 650:
                    self.feel("impact", 0.6)
                    self.dizzy_t = max(self.dizzy_t, 0.8)
                self.squash.impulse(min(9.0, self.vy * 0.012))
                self.wobble = max(self.wobble, 0.04)
                if self.vy < 160:
                    self.vy = 0.0
                    self.mode = self.IDLE
                    self.decide_in = random.uniform(*C.IDLE_TIME)
                else:
                    self.vy = -self.vy * 0.35

        # mantenerse dentro de alguna pantalla (salvo arrastrando)
        if screens and self.mode not in (self.DRAG, self.PERCH):
            m = self.R * 1.15
            best, bd, br = None, None, None
            for r in screens:
                nx = clamp(self.x, r[0] + m, r[0] + r[2] - m)
                ny = clamp(self.y, r[1] + m, r[1] + r[3] - m)
                d = (nx - self.x) ** 2 + (ny - self.y) ** 2
                if bd is None or d < bd:
                    best, bd, br = (nx, ny), d, r
            if bd and bd > 0.01:
                bx, by = best
                speed = math.hypot(self.vx, self.vy)
                if self.mode == self.THROWN and speed > 550:
                    # choco fuerte contra el borde: se aplasta y pone ojos ><
                    nx, ny = bx - self.x, by - self.y
                    n = math.hypot(nx, ny) or 1.0
                    self.stretch.a.impulse(nx / n * speed * 0.004)
                    self.stretch.b.impulse(ny / n * speed * 0.004)
                    self.feel("impact", 0.7)
                    self.sfx.append("bonk")
                    self.dizzy_t = max(self.dizzy_t, 1.0)
                    self.wobble = max(self.wobble, 0.05)
                if (bx - self.x) * self.vx < 0:
                    self.vx *= -0.35
                if (by - self.y) * self.vy < 0:
                    self.vy *= -0.35
                self.x = approach(self.x, bx, 9.0, dt)
                self.y = approach(self.y, by, 9.0, dt)
                if self.mode == self.WANDER and self.target and self.perch_goal is None:
                    self.target = (clamp(self.target[0], br[0] + m, br[0] + br[2] - m),
                                   clamp(self.target[1], br[1] + m, br[1] + br[3] - m))

    def _arrive(self):
        """Llego a su destino: si iba a una ventana, se posa."""
        if self.perch_goal is None:
            return
        r = self.perch_rect
        hwnd = self.perch_goal
        self.perch_goal = None
        if r is None:
            return
        if r[0] - 4 <= self.x <= r[0] + r[2] + 4 and abs(self.y - (r[1] - self.R * 0.92)) < self.R * 0.8:
            self.perch = {"hwnd": hwnd, "off": self.x - r[0]}
            self.perch_time = random.uniform(15.0, 45.0) * (1.4 if self.energy() < 0.9 else 1.0)
            self.mode = self.PERCH
            self.sfx.append("hop")
            self.squash.impulse(4.0)
            self.feel("proud", 1.2)

    # ------------------------------------------------------------ cara
    def _expressions(self, dt, dist, near):
        self.need_sad = approach(self.need_sad, self.need_target[0], 0.8, dt)
        self.need_angry = approach(self.need_angry, self.need_target[1], 0.8, dt)
        # al abrir (o al saludar), los planetas giran rapido y de a poco vuelven a su ritmo
        boost = 1.0 + 10.0 * max(0.0, 1.0 - self.spin_t / 4.0) ** 2
        self.orbit_phase += dt * boost
        self._swallow_step(dt)
        if self.orbit:
            for k in ("new", "moon_new"):
                if self.orbit.get(k, 0) > 0:
                    self.orbit[k] = max(0.0, self.orbit[k] - dt)
        if near and self.cursor_still > 0:
            self.near_still += dt
        else:
            self.near_still = 0.0
        self.cuddle_cd = max(0.0, self.cuddle_cd - dt)
        self.align_t = max(0.0, self.align_t - dt)
        if ("cuddle" in self.unlocks and self.near_still > C.CUDDLE_STILL and self.cuddle_cd <= 0
                and dist > self.R * 1.4 and self.anchor is None and not self.asleep
                and self.mode in (self.IDLE, self.WANDER)):
            self._cuddle()
        elif self.near_still > 6.0 and dist > self.R * 2.5:
            self.feel("suspicious", 2.5)          # cursor quieto cerca mucho rato: lo mira de reojo
            self.near_still = -6.0
        for k in EXPRESSIONS:
            hold = self.expr_hold[k]
            if hold > 0:
                self.expr_hold[k] = max(0.0, hold - dt)
            self.expr[k] = approach(self.expr[k], 1.0 if hold > 0 else 0.0, 9.0 if hold > 0 else 4.0, dt)
        if self.wink_t >= 0:
            self.wink_t += dt
            if self.wink_t > 0.35:
                self.wink_t = -1.0
        if self.celebrate_t > 0:
            self.celebrate_t -= dt
            self.celebrate_bounce -= dt
            if self.celebrate_bounce <= 0:
                self.hop.impulse(-170)
                self.squash.impulse(6.0)
                self.celebrate_bounce = 0.5
        if self.pet_time > 3.0:
            self.feel("love", 0.6)                # caricia larga: ojos de corazon
        self._pinned_moods(dt)

    MOOD_PICKS = {
        "feliz": ["happy", "happy", "happy", "wink", "proud", "excited", "glance", "dance", "surprised", "swallow"],
        "carinoso": ["love", "love", "happy", "happy", "wink", "dance", "swallow"],
        "contento": ["happy", "happy", "curious", "wink", "glance", "proud", "puzzled", "surprised", "dance",
                     "swallow"],
        "aburrido": ["glance", "glance", "sad", "sigh", "suspicious", "curious", "seek", "puzzled", "stretch"],
        "cansado": ["sleepy", "sleepy", "sleepy", "glance", "stretch"],
        "con_sueno": ["sleepy", "sleepy", "sleepy", "sleepy", "glance"],
        "molesto": ["glare", "serious", "suspicious", "pout", "glance"],
        "triste": ["sad", "sad", "sad", "glance", "sigh"],
    }

    def _pinned_moods(self, dt):
        """Va cambiando de animo segun lo que siente (corazon) y lo que estas haciendo."""
        if self.mode not in (self.IDLE, self.PERCH) or self.asleep:
            return
        if max(self.expr_hold.values()) > 0 or self.happy_time > 0:
            return                                 # ya esta expresando algo
        self.mood_in -= dt
        if self.mood_in > 0:
            return
        pinned = self.anchor is not None
        self.mood_in = random.uniform(7.0, 16.0) if pinned else random.uniform(14.0, 30.0)
        own = self.MOOD_PICKS.get(self.temper, self.MOOD_PICKS["contento"])
        if self.typing > 0.5 and random.random() < 0.6:     # escribiendo: concentrado, orgulloso de ti
            pick = random.choice(["serious", "serious", "proud", "curious", "nod"])
        elif self.activity > 0.4 and random.random() < 0.5:  # moviendo el mouse: atento
            pick = random.choice(["curious", "excited", "happy", "glance", "wink"])
        else:
            pick = random.choice(own)
        if pick == "happy":
            self.happy.target = 1.0
            self.happy_time = 1.6
        elif pick == "wink":
            self.wink_t = 0.0
            self.wink_side = random.choice((-1, 1))
            self.sfx.append("giggle")
        elif pick == "sleepy":
            self.sleepy_hold = 3.5
        elif pick == "sigh":                       # suspiro: se desinfla un poco
            self.squash.impulse(-4.0)
            self.sleepy_hold = 1.5
        elif pick == "pout":                       # puchero: enojo cortito, sin ruido
            self.expr_hold["angry"] = 1.4
        elif pick == "seek":                       # aburrido: te busca con la mirada
            self.feel("curious", 1.5)
            self.hop.impulse(-60)
        elif pick == "nod":                        # asiente al ritmo de lo que escribes
            self.hop.impulse(-70)
            self.squash.impulse(3.0)
        elif pick == "puzzled":                    # extranado: ladea la cabeza, un ojo grande y un "?"
            self.feel("puzzled", 2.4)
            self.fx.emit("q", self.R)
        elif pick == "surprised":                  # sorprendido: ojos grandes y saltito
            self.wide.impulse(7.0)
            self.hop.impulse(-130)
            self.feel("excited", 0.8)
            self.sfx.append("eep")
        elif pick == "stretch":                    # se despereza: se estira hacia arriba
            self.squash.impulse(-11.0)
            self.sleepy_hold = 1.4
            self.happy.target = 0.5
            self.happy_time = 1.0
        elif pick == "swallow":                    # broma: se traga sus planetas y los escupe
            if self.can_swallow():
                self.swallow_planets()
            else:
                self.happy.target = 1.0
                self.happy_time = 1.4
        elif pick == "dance":                      # bailecito de lado a lado
            self.dance_t = 1.8
            self.happy.target = 1.0
            self.happy_time = 1.9
        elif pick == "glance":                     # se distrae mirando a otro lado
            ang = random.uniform(0, 2 * math.pi)
            self.look_at_pt = (self.x + math.cos(ang) * 600, self.y + math.sin(ang) * 400)
            self.look_at_t = 1.8
        else:
            self.feel(pick, random.uniform(1.5, 3.0))


    def _deform(self, dt, dx, dy, dist, near):
        gain = 0.0017 * (30.0 / self.R) ** 0.3
        sx, sy = self.vx * gain, self.vy * gain
        mag = math.hypot(sx, sy)
        if mag > 0.33:
            sx, sy = sx / mag * 0.33, sy / mag * 0.33
        self.stretch.set_target(sx, sy)
        self.stretch.step(dt)

        self.squash.target = 0.10 if (self.asleep or self.mode == self.PERCH) else 0.0
        self.squash.step(dt)
        self.squash.x = clamp(self.squash.x, -0.45, 0.55)
        self.hop.step(dt)
        if self.hop.x > 0:
            self.hop.x, self.hop.v = 0.0, -self.hop.v * 0.3

        lean = clamp(self.vx * 0.0022, -0.22, 0.22) if self.mode != self.PERCH else 0.0
        if near and self.mode == self.IDLE and dist > 1:
            lean += clamp(dx / dist, -1, 1) * 0.07
        if self.dizzy_t > 0:
            lean += math.sin(self.t * 5.0) * 0.14 * min(1.0, self.dizzy_t)
            self.wobble = max(self.wobble, 0.03)
        if self.pet > 0.05:
            lean += math.sin(self.t * 3.0) * 0.05 * self.pet
        if self.headshake_t > 0:                  # niega con el cuerpo
            self.headshake_t -= dt
            lean += math.sin(self.t * 7.0) * 0.12
        lean += 0.12 * self.expr["curious"]       # ladea la cabeza cuando tiene curiosidad
        lean += 0.2 * self.expr["puzzled"]        # extranado: cabeza bien ladeada
        if self.dance_t > 0:                      # bailecito
            self.dance_t -= dt
            lean += math.sin(self.t * 9.0) * 0.16
            if int(self.t * 4.5) != int((self.t - dt) * 4.5):
                self.hop.impulse(-55)
        self.lean.target = lean
        self.lean.step(dt)

        base = 0.010 if self.mode in (self.IDLE, self.PERCH) else 0.018
        self.wobble = approach(self.wobble, base, 1.8, dt)

        floating = self.mode in (self.IDLE, self.WANDER)
        e = self.energy()
        calm_amp = 0.3 if self.asleep else (0.55 if self.sleepy > 0.5 else 0.7 + 0.3 * min(1.0, e))
        self.bob_amp = approach(self.bob_amp, calm_amp if floating else 0.0, 3.0, dt)

    def _face(self, dt, dx, dy, dist, near):
        def toward(px, py, k=4.5):
            ddx, ddy = px - self.x, py - self.y
            return (clamp(math.atan2(ddx, self.R * k) * 1.15, -C.S["max_yaw"], C.S["max_yaw"]),
                    clamp(math.atan2(-ddy, self.R * k) * 1.1, -0.55, 0.85))

        if self.asleep:
            ty, tp = 0.15, -0.1
        elif self.swallow_t >= 0:
            ty, tp = 0.0, 0.12                     # en la broma mira de frente (se le ve la boca)
        elif self.dizzy_t > 0:
            ty = 0.45 * math.cos(self.t * 6.5)
            tp = 0.3 + 0.28 * math.sin(self.t * 6.5)
        elif self.expr["impact"] > 0.5:
            ty, tp = 0.0, 0.3
        elif self.mode in (self.DRAG, self.THROWN, self.FALL):
            ty = clamp(self.vx * 0.003, -0.9, 0.9)
            tp = clamp(-self.vy * 0.002 + 0.25, -0.5, 0.8)
        elif self.expr["suspicious"] > 0.3:
            ty, tp = toward(*self.cursor_prev)
            ty = clamp(ty * 1.4, -C.S["max_yaw"], C.S["max_yaw"])
            tp *= 0.4
        elif self.look_at_t > 0 and self.look_at_pt is not None:
            ty, tp = toward(*self.look_at_pt, k=6.0)
        elif near or self.typing > 0.5:
            ty, tp = toward(self.x + dx, self.y + dy)
        elif self.anchor is not None and self.mode == self.IDLE:
            ty, tp = toward(self.x + dx, self.y + dy, k=7.0)      # fijo: te sigue por toda la pantalla
        elif self.mode == self.WANDER:
            sp = math.hypot(self.vx, self.vy) + 1e-3
            ty = clamp(self.vx / sp * 0.7, -0.8, 0.8)
            tp = clamp(-self.vy / sp * 0.5 + 0.25, -0.4, 0.75)
        else:
            self.glance_in -= dt
            if self.glance_in <= 0:
                opts = [(C.FACE_YAW, C.FACE_PITCH)] * 4 + [(-0.45, 0.4), (0.05, 0.6), (0.65, 0.1), (-0.2, 0.15)]
                if self.mode == self.PERCH:
                    opts += [(0.3, -0.4), (-0.4, -0.35), (0.0, -0.45)]      # mira hacia abajo desde arriba
                self.glance = random.choice(opts)
                self.glance_in = random.uniform(2.0, 6.0)
            ty, tp = self.glance
            self.micro_in -= dt
            if self.micro_in <= 0:
                self.micro = (random.uniform(-0.07, 0.07), random.uniform(-0.05, 0.05))
                self.micro_in = random.uniform(0.35, 1.4)
            ty += self.micro[0]
            tp += self.micro[1]
        if self.look_at_t > 0:
            self.look_at_t -= dt
        tp -= 0.35 * self.sleepy + 0.3 * self.expr["sad"] + 0.18 * self.need_sad
        self.yaw.target, self.pitch.target = ty, tp
        self.yaw.step(dt)
        self.pitch.step(dt)

        # parpadeo
        if self.asleep:
            self.blink_t = -1.0
        elif self.blink_t >= 0:
            self.blink_t += dt
            if self.blink_t > 0.15:
                self.blink_t = -1.0
                if self.double_blink:
                    self.double_blink = False
                    self.blink_in = 0.12
                else:
                    self.blink_in = random.uniform(2.0, 5.5)
        else:
            self.blink_in -= dt
            if self.blink_in <= 0:
                self.blink_t = 0.0
                self.double_blink = random.random() < 0.2

        # emociones base
        if self.happy_time > 0:
            self.happy_time -= dt
            if self.happy_time <= 0:
                self.happy.target = 0.0
        self.happy.step(dt)
        if self.mode != self.DRAG:
            self.wide.target = 0.15 * self.typing + 0.35 * self.expr["excited"]
        self.wide.step(dt)
        if self.sleepy_hold > 0:
            self.sleepy_hold -= dt
        sleepy_target = 1.0 if self.sleepy_hold > 0 or (self.since_interaction > C.SLEEPY_AFTER * (0.5 if self.energy() < 0.6 else 1.0)
                                and self.mode == self.IDLE) else 0.0
        self.sleepy = approach(self.sleepy, sleepy_target, 0.6 if sleepy_target else 4.0, dt)

    # =========================================================== render data
    def _align_amount(self):
        t = self.align_t
        if t <= 0:
            return 0.0
        k = min(1.0, (C.ALIGN_SECONDS - t) / 1.2, t / 1.2)
        return k * k * (3 - 2 * k)

    def eye_open(self):
        if self.blink_t < 0:
            return 1.0
        return 1.0 - 0.88 * math.sin(math.pi * clamp(self.blink_t / 0.15, 0, 1))

    def pose(self):
        e = self.expr
        breath_speed = 1.0 if self.asleep else (1.4 if self.sleepy > 0.5 else 2.1)
        amp = 0.036 if self.asleep else (0.028 if self.mode in (self.IDLE, self.PERCH) else 0.014)
        breath = math.sin(self.t * breath_speed) * amp - 0.05 * self.puff     # inflado: mas ancho
        base_open = 0.08 if self.asleep else self.eye_open() * (1.0 - 0.4 * self.sleepy) * (1.0 - 0.5 * self.pet)
        if self.yawn_t > 0:                        # bostezo: entrecierra los ojos
            base_open *= 1.0 - 0.75 * math.sin(min(1.0, (1.4 - self.yawn_t) / 1.4) * math.pi)
        happy = max(self.happy.x, 0.9 * self.pet, 0.8 * e["proud"])

        ns, na = (0.0, 0.0) if self.asleep else (self.need_sad, self.need_angry)
        lid = (0.45 * e["glare"] + 0.3 * e["serious"] + 0.3 * e["sad"] + 0.42 * e["angry"]
               + 0.22 * ns + 0.3 * na)
        lid_angle = 20 * e["serious"] - 22 * e["sad"] + 30 * e["angry"] - 20 * ns + 38 * na
        arc = happy > 0.55 and e["angry"] < 0.3 and e["sad"] < 0.3 and max(ns, na) < 0.5
        eyes = []
        for side in (-1, 1):
            if e["impact"] > 0.5:
                shape = "chevron"
            elif e["love"] > 0.5:
                shape = "heart"
            elif arc:
                shape = "arc"
            else:
                shape = "ellipse"
            eye = {
                "open": base_open,
                "lid": lid + e["suspicious"] * (0.45 if side == -1 else 0.1) + e["puzzled"] * (0.32 if side == -1 else 0.0),
                "lid_angle": lid_angle - 10 * e["suspicious"] - 14 * e["puzzled"],
                "low_lid": 0.28 * e["proud"],
                "scale": 1.0 + e["curious"] * (0.14 if side == 1 else -0.08) + 0.1 * e["excited"]
                         + e["puzzled"] * (0.16 if side == 1 else -0.12)
                         + 0.12 * e["love"],
                "shape": shape,
            }
            if self.wink_t >= 0 and side == self.wink_side:
                eye["open"] = 0.12
                eye["shape"] = "ellipse"
            eyes.append(eye)

        return {
            "R": self.R,
            "bob": math.sin(self.t * 1.7) * self.R * 0.07 * self.bob_amp,
            "hop": self.hop.x,
            "lean": self.lean.x,
            "stretch": self.stretch.value,
            "squash": self.squash.x,
            "breath": breath,
            "wobble": self.wobble,
            "t": self.t,
            "yaw": self.yaw.x,
            "pitch": self.pitch.x,
            "open": base_open,
            "happy": clamp(happy, 0.0, 1.2),
            "wide": clamp(self.wide.x, -0.3, 1.2),
            "alpha": self.alpha,
            "eyes": eyes,
            "blush": clamp(max(0.8 * self.pet, e["love"], 0.6 * e["proud"], 0.9 * self.puff), 0.0, 1.0),
            "tears": e["sad"],
            "shadow": self.mode != self.PERCH,
            "fx": self.fx.pose(),
            "hat": self.hat,
            "mouth": (self.mouth_shape, self.mouth_open) if self.mouth_shape else None,
            "lumps": self._lumps(),
            "orbit": (dict(self.orbit, phase=self.orbit_phase, align=self._align_amount(), appear=self.boot_t,
                           swallow=self.swallow_t, mouth=self.mouth_pos) if self.orbit else None),
        }
