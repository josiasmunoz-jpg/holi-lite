"""
Necesidades y confianza de Holi.

  hambre  aparece una vez al dia, despues de un rato de uso. Se soluciona con "Dar comida".
  sueño   aparece una vez al dia, despues de varias horas de uso. Se soluciona con "Mandar a dormir":
          duerme unos minutos y despierta solo.

Si no lo atiendes: primero reclama, despues se pone triste y despues enojado, y se queda asi
hasta que lo soluciones. Nunca se muere. Los tiempos solo corren con Holi abierto, asi que
el tiempo con el PC apagado no lo hace enojarse.

Confianza: sube con el tiempo que pasan juntos y cuando lo cuidas. Nunca baja; si esta
triste o enojado simplemente deja de subir. Se ve como planetas que orbitan a Holi: cada
planeta nace chiquitito y crece en GROW_STAGES etapas; cuando termina de crecer nace el
siguiente. El color de cada planeta lo eliges tu. Con los 5 planetas listos la confianza sigue:
cada planeta gana una luna, del primero al ultimo.

Dias juntos: cuantos dias distintos han pasado tiempo juntos.
"""
import datetime as dt
import json
import random

from . import config as C

PLANET_COLORS = [
    ("Naranjo", "#ff8a3d"),
    ("Celeste", "#5ec8ff"),
    ("Rosado", "#ff6fa8"),
    ("Verde", "#5fd68a"),
    ("Morado", "#a77bff"),
    ("Amarillo", "#ffd45c"),
    ("Rojo", "#ff5a5a"),
    ("Blanco", "#f2f2f5"),
    ("Negro", "#16161a"),
]


def _speed():
    return C.FAST_FACTOR if C.S.get("fast_mode") else 1.0


def _day_key():
    """Clave del 'dia'. En modo prueba un dia dura FAST_DAY_SECONDS."""
    if C.S.get("fast_mode"):
        return "t%d" % int(dt.datetime.now().timestamp() // C.FAST_DAY_SECONDS)
    return dt.date.today().isoformat()


class Needs:
    def __init__(self):
        self.day = _day_key()
        self.used_today = 0.0          # minutos con Holi abierto hoy
        self.fed_day = None            # dia en que ya comio
        self.slept_day = None          # dia en que ya durmio su siesta
        self.hungry = False
        self.sleepy = False
        self.hunger_age = 0.0          # minutos que lleva con hambre (solo con Holi abierto)
        self.sleep_age = 0.0
        self.nap_left = 0.0            # segundos de siesta que quedan
        self.trust = 0.0               # puntos de confianza acumulados (nunca bajan)
        self.planet_colors = []        # colores de los planetas ganados
        self.reclaim_in = 0.0          # minutos para el proximo reclamo
        self.days = 1                  # dias distintos con Holi abierto
        self.pending = []              # eventos para el controlador: "reclaim", "star", "planet", "woke"

    # ------------------------------------------------------------ guardar
    def dump(self):
        return json.dumps({
            "day": self.day, "used": round(self.used_today, 2), "fed": self.fed_day, "slept": self.slept_day,
            "hungry": self.hungry, "sleepy": self.sleepy, "hage": round(self.hunger_age, 2),
            "sage": round(self.sleep_age, 2), "trust": round(self.trust, 2), "planets": self.planet_colors,
            "days": self.days,
        })

    def restore(self, text):
        try:
            d = json.loads(text or "{}")
        except (TypeError, ValueError):
            return
        try:
            self.day = d.get("day", self.day)
            self.used_today = float(d.get("used", 0.0))
            self.fed_day = d.get("fed")
            self.slept_day = d.get("slept")
            self.hungry = bool(d.get("hungry", False))
            self.sleepy = bool(d.get("sleepy", False))
            self.hunger_age = float(d.get("hage", 0.0))
            self.sleep_age = float(d.get("sage", 0.0))
            self.trust = max(0.0, float(d.get("trust", 0.0)))
            self.planet_colors = [str(c) for c in d.get("planets", [])][:C.MAX_PLANETS]
            self.days = max(1, int(d.get("days", 1)))
        except (TypeError, ValueError):
            pass
        self.planet_colors = self.planet_colors[:self.visible_planets()]
        while len(self.planet_colors) < self.visible_planets():
            self.planet_colors.append(self._new_color())

    # ------------------------------------------------------------ confianza
    @staticmethod
    def star_cost(planet_index):
        """Puntos por estrella; cada planeta nuevo cuesta mas que el anterior."""
        return C.STAR_POINTS * (1.0 + C.PLANET_GROWTH * planet_index)

    def _progress(self):
        """(planetas que ya terminaron de crecer, etapa del planeta que esta creciendo 0..GROW_STAGES-1)."""
        pts = self.trust
        planets = 0
        while planets < C.MAX_PLANETS:
            cost = self.star_cost(planets) * C.GROW_STAGES
            if pts < cost:
                return planets, int(pts // self.star_cost(planets))
            pts -= cost
            planets += 1
        return planets, 0

    def planets_earned(self):
        """Planetas que ya terminaron de crecer."""
        return self._progress()[0]

    def stars(self):
        """Etapa del planeta que esta creciendo (0 = todavia no nace)."""
        return self._progress()[1]

    def visible_planets(self):
        """Planetas que se ven: los grandes mas el que esta creciendo (si ya nacio)."""
        done, stage = self._progress()
        return done + (1 if stage > 0 and done < C.MAX_PLANETS else 0)

    def planet_sizes(self):
        """Radio de cada planeta visible, relativo al radio de Holi."""
        done, stage = self._progress()
        sizes = []
        for i in range(self.visible_planets()):
            var = C.PLANET_SIZE_VAR[i % len(C.PLANET_SIZE_VAR)]
            st = C.GROW_STAGES if i < done else stage
            sizes.append(C.PLANET_SIZES[st - 1] * var)
        return sizes

    def maxed(self):
        """Los 5 planetas terminaron de crecer."""
        return self.planets_earned() >= C.MAX_PLANETS

    def _planets_cost(self):
        return sum(self.star_cost(k) * C.GROW_STAGES for k in range(C.MAX_PLANETS))

    def moons(self):
        """Lunas ganadas despues de los 5 planetas (una por planeta)."""
        if not self.maxed():
            return 0
        return min(C.MAX_PLANETS, int((self.trust - self._planets_cost()) // C.MOON_POINTS))

    def moon_progress(self):
        """0..1 hacia la proxima luna."""
        if not self.maxed() or self.moons() >= C.MAX_PLANETS:
            return 0.0
        return ((self.trust - self._planets_cost()) % C.MOON_POINTS) / C.MOON_POINTS

    def complete(self):
        return self.moons() >= C.MAX_PLANETS

    def _new_color(self):
        used = set(self.planet_colors)
        pool = [h for _, h in PLANET_COLORS if h not in ("#f2f2f5", "#16161a")]   # blanco y negro solo si los eliges tu
        free = [h for h in pool if h not in used] or pool
        return random.choice(free)

    def add_trust(self, pts):
        if pts <= 0 or self.complete():
            return
        before, moons = self._progress(), self.moons()
        self.trust += pts
        after = self._progress()
        if self.moons() > moons:
            self.pending.append("moon")           # un planeta gano su luna
        while len(self.planet_colors) < self.visible_planets():
            self.planet_colors.append(self._new_color())
        if after[0] > before[0]:
            self.pending.append("planet")         # termino de crecer
        elif after[1] > before[1]:
            self.pending.append("star")           # crecio una etapa (o nacio uno nuevo)

    # ------------------------------------------------------------ estado
    def napping(self):
        return self.nap_left > 0

    def stage(self, kind):
        """0 nada, 1 reclama, 2 triste, 3 enojado."""
        if kind == "hunger":
            on, age = self.hungry, self.hunger_age
        else:
            on, age = self.sleepy and not self.napping(), self.sleep_age
        if not on:
            return 0
        if age >= C.NEED_ANGRY_AFTER:
            return 3
        if age >= C.NEED_SAD_AFTER:
            return 2
        return 1

    def worst(self):
        """(etapa, tipo) de la necesidad mas urgente."""
        h, s = self.stage("hunger"), self.stage("sleep")
        if h == 0 and s == 0:
            return 0, None
        return (h, "hunger") if h >= s else (s, "sleep")

    # ------------------------------------------------------------ acciones
    def feed(self):
        """Devuelve True si tenia hambre."""
        if not self.hungry:
            return False
        bonus = C.TRUST_CARE if self.stage("hunger") <= 1 else C.TRUST_CARE_LATE
        self.hungry = False
        self.hunger_age = 0.0
        self.fed_day = self.day
        self.reclaim_in = 0.0
        self.add_trust(bonus)
        return True

    def put_to_sleep(self):
        """Devuelve True si tenia sueño (y empieza la siesta)."""
        if not self.sleepy or self.napping():
            return False
        bonus = C.TRUST_CARE if self.stage("sleep") <= 1 else C.TRUST_CARE_LATE
        self.nap_left = C.NAP_SECONDS / _speed()
        self.add_trust(bonus)
        return True

    # ------------------------------------------------------------ tiempo
    def update(self, dt_s, present):
        """dt_s: segundos reales con Holi activo. present: el usuario esta usando el PC."""
        k = _speed()
        mins = dt_s / 60.0 * k

        today = _day_key()
        if today != self.day:
            self.day = today
            self.used_today = 0.0
            self.days += 1
        self.used_today += mins

        if self.nap_left > 0:
            self.nap_left -= dt_s
            if self.nap_left <= 0:
                self.nap_left = 0.0
                self.sleepy = False
                self.sleep_age = 0.0
                self.slept_day = self.day
                self.pending.append("woke")

        if not self.hungry and self.fed_day != self.day and self.used_today >= C.HUNGRY_AFTER_USE:
            self.hungry = True
            self.hunger_age = 0.0
            self.reclaim_in = 0.0
        if (not self.sleepy and self.slept_day != self.day and self.used_today >= C.SLEEPY_AFTER_USE):
            self.sleepy = True
            self.sleep_age = 0.0
            self.reclaim_in = min(self.reclaim_in, 0.5)

        if self.hungry:
            self.hunger_age += mins
        if self.sleepy and not self.napping():
            self.sleep_age += mins

        stage, _ = self.worst()
        if stage:
            self.reclaim_in -= mins
            if self.reclaim_in <= 0:
                self.reclaim_in = C.RECLAIM_EVERY
                self.pending.append("reclaim")

        # confianza: tiempo juntos (si esta triste o enojado, no sube)
        if present and stage <= 1:
            self.add_trust(mins * C.TRUST_PER_MINUTE)

    def take_events(self):
        ev, self.pending = self.pending, []
        return ev
