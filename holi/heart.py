"""
Corazon de Holi: su estado interno, que cambia solo con el tiempo y con lo que le haces.

  energia    0..1  sube en la manana, baja de noche, se recupera durmiendo
  animo      0..1  sube con cariño y clics; baja si lo molestas o lo ignoras mucho
  cariño     0..1  sube con caricias; baja lento si no lo pescas
  aburrimiento 0..1 sube cuando nadie le hace caso; baja cuando lo tocas

Con eso se calcula un "sentimiento" dominante que el modelo usa para sus gestos.
"""
import datetime as dt
import json


def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def _toward(v, target, rate, dt_s):
    """Acerca v a target a 'rate' unidades por hora."""
    step = rate * dt_s / 3600.0
    if v < target:
        return min(target, v + step)
    return max(target, v - step)


class Heart:
    def __init__(self):
        self.energy = 0.8
        self.mood = 0.65
        self.affection = 0.5
        self.boredom = 0.2

    # ------------------------------------------------------------ guardar
    def dump(self):
        return json.dumps({"energy": round(self.energy, 3), "mood": round(self.mood, 3),
                           "affection": round(self.affection, 3), "boredom": round(self.boredom, 3),
                           "seen": dt.datetime.now().isoformat(timespec="seconds")})

    def restore(self, text):
        try:
            d = json.loads(text or "{}")
        except (TypeError, ValueError):
            return
        self.energy = _clamp(float(d.get("energy", self.energy)))
        self.mood = _clamp(float(d.get("mood", self.mood)))
        self.affection = _clamp(float(d.get("affection", self.affection)))
        self.boredom = _clamp(float(d.get("boredom", self.boredom)))
        try:
            seen = dt.datetime.fromisoformat(d["seen"])
        except (KeyError, TypeError, ValueError):
            return
        hours = max(0.0, (dt.datetime.now() - seen).total_seconds() / 3600.0)
        if hours > 6:                  # durmio: vuelve con energia, algo extrañado
            self.energy = max(self.energy, 0.85)
            self.boredom = min(0.4, 0.15 + hours / 100.0)
            self.mood = max(self.mood, 0.55)
        if hours > 48:                 # te echo de menos
            self.affection = max(0.3, self.affection - 0.1)

    # ------------------------------------------------------------ eventos
    def event(self, kind):
        e = {
            "click": (0.00, 0.01, 0.00, -0.08),
            "pet": (0.00, 0.03, 0.03, -0.15),
            "thrown": (-0.02, -0.02, -0.01, -0.10),
            "annoyed": (0.00, -0.12, -0.04, -0.10),
            "wake": (0.05, 0.00, 0.00, 0.00),
        }.get(kind)
        if not e:
            return
        self.energy = _clamp(self.energy + e[0])
        self.mood = _clamp(self.mood + e[1])
        self.affection = _clamp(self.affection + e[2])
        self.boredom = _clamp(self.boredom + e[3])

    # ------------------------------------------------------------ tiempo
    def update(self, dt_s, hour, since_interaction, asleep, typing, petting):
        # energia: sigue el reloj; dormir recarga
        if 6 <= hour < 12:
            target = 0.95
        elif 12 <= hour < 15:
            target = 0.75
        elif 15 <= hour < 19:
            target = 0.7
        elif 19 <= hour < 23:
            target = 0.5
        else:
            target = 0.25
        self.energy = _toward(self.energy, 1.0 if asleep else target, 1.2 if asleep else 0.35, dt_s)

        # aburrimiento: sube si nadie lo pesca (mas lento si estas escribiendo: te esta mirando trabajar)
        if since_interaction > 120 and not asleep:
            self.boredom = _toward(self.boredom, 1.0, 0.45 if typing > 0.5 else 0.9, dt_s)
        elif since_interaction < 10:
            self.boredom = _toward(self.boredom, 0.0, 1.5, dt_s)

        # cariño: caricias lo suben, con el tiempo vuelve lento a la mitad
        if petting > 0.5:
            self.affection = _clamp(self.affection + 0.04 * dt_s)
        self.affection = _toward(self.affection, 0.5, 0.03, dt_s)

        # animo: tiende a un punto de equilibrio que depende de lo demas
        base = 0.55 + 0.25 * (self.affection - 0.5) - 0.3 * max(0.0, self.boredom - 0.5) + 0.1 * (self.energy - 0.5)
        self.mood = _toward(self.mood, _clamp(base), 0.25, dt_s)

    # ------------------------------------------------------------ lectura
    def feeling(self, hour=12.0):
        if self.mood < 0.3:
            return "molesto" if self.boredom < 0.5 else "triste"
        if self.energy < 0.3:
            return "con_sueno" if (hour >= 22 or hour < 6) else "cansado"
        if self.boredom > 0.7:
            return "aburrido"
        if self.affection > 0.75 and self.mood > 0.6:
            return "carinoso"
        if self.mood > 0.75:
            return "feliz"
        return "contento"
