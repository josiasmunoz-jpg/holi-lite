"""
Ruiditos de Holi, sintetizados (sin archivos de terceros). Se generan como .wav en
%APPDATA%\\HoliLite\\sounds la primera vez y se reproducen sin bloquear con winsound.
"""
import io
import math
import os
import random
import struct
import sys
import time
import wave

SR = 22050

# cada sonido: lista de "notas" (inicio_s, dur_s, f0, f1, forma)
# f0 -> f1 es un barrido de tono; forma: "sine" (suave) o "bloop" (con un poco de armonico)
SOUNDS = {
    "boop":    [(0.0, 0.10, 520, 820, "bloop")],                        # clic: bup!
    "giggle":  [(0.0, 0.07, 700, 980, "bloop"), (0.09, 0.08, 760, 1100, "bloop")],
    "wee":     [(0.0, 0.26, 600, 1400, "sine")],                        # lo lanzas: uiii
    "eep":     [(0.0, 0.07, 1300, 1700, "bloop")],                      # susto
    "bonk":    [(0.0, 0.11, 300, 160, "bloop")],                        # choque / aterrizaje
    "yawn":    [(0.0, 0.45, 520, 300, "sine")],                         # despierta
    "purr":    [(0.0, 0.40, 210, 230, "purr")],                         # caricia
    "love":    [(0.0, 0.08, 880, 880, "sine"), (0.08, 0.08, 1108, 1108, "sine"), (0.16, 0.14, 1318, 1318, "sine")],
    "aww":     [(0.0, 0.35, 620, 380, "sine")],                         # triste
    "grr":     [(0.0, 0.28, 170, 150, "grr")],                          # enojado
    "tada":    [(0.0, 0.09, 660, 660, "bloop"), (0.1, 0.09, 830, 830, "bloop"), (0.2, 0.18, 990, 990, "bloop")],
    "pip":     [(0.0, 0.05, 900, 1200, "bloop")],                       # escupe un planeta
    "hop":     [(0.0, 0.08, 480, 640, "bloop")],                        # se posa en una ventana
    "gulp":    [(0.0, 0.16, 420, 150, "bloop"), (0.22, 0.09, 330, 560, "bloop")],   # se traga algo
}

# cuanto esperar antes de repetir el mismo sonido (para que no moleste)
COOLDOWN = {"purr": 1.4, "bonk": 0.4, "pip": 0.2, "eep": 0.8}


def _render(notes, volume):
    total = max(s + d for s, d, *_ in notes) + 0.03
    n = int(total * SR)
    buf = [0.0] * n
    for start, dur, f0, f1, shape in notes:
        i0 = int(start * SR)
        m = int(dur * SR)
        phase = 0.0
        for i in range(m):
            t = i / m
            f = f0 * (f1 / f0) ** t                       # barrido exponencial (suena natural)
            if shape == "purr":
                f *= 1 + 0.04 * math.sin(2 * math.pi * 28 * i / SR)
            phase += 2 * math.pi * f / SR
            if shape == "bloop":
                v = math.sin(phase) + 0.25 * math.sin(2 * phase)
            elif shape == "purr":
                v = math.sin(phase) * (0.55 + 0.45 * math.sin(2 * math.pi * 24 * i / SR))
            elif shape == "grr":
                v = math.sin(phase) + 0.35 * math.sin(3 * phase) + 0.15 * (random.random() - 0.5)
            else:
                v = math.sin(phase)
            att = min(1.0, i / (0.008 * SR))              # entrada suave
            rel = min(1.0, (m - i) / (0.04 * SR))         # salida suave
            env = att * rel * (1 - 0.35 * t)
            if i0 + i < n:
                buf[i0 + i] += v * env
    peak = max(1e-6, max(abs(x) for x in buf))
    gain = volume / peak
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x * gain)) * 32000)) for x in buf))
    return out.getvalue()


class SoundBank:
    def __init__(self, folder, volume=0.35):
        self.folder = folder
        self.volume = volume
        self.last = {}
        self.last_any = 0.0
        self.ready = False
        os.makedirs(folder, exist_ok=True)

    def path(self, name):
        return os.path.join(self.folder, "%s_%02d.wav" % (name, int(self.volume * 100)))

    def prepare(self):
        """Genera los .wav que falten (una sola vez por volumen)."""
        for name, notes in SOUNDS.items():
            p = self.path(name)
            if not os.path.exists(p):
                try:
                    with open(p, "wb") as fh:
                        fh.write(_render(notes, self.volume))
                except OSError:
                    pass
        self.ready = True

    def play(self, name):
        if not self.ready or name not in SOUNDS or not sys.platform.startswith("win"):
            return
        now = time.monotonic()
        if now - self.last.get(name, 0) < COOLDOWN.get(name, 0.12) or now - self.last_any < 0.08:
            return
        self.last[name] = now
        self.last_any = now
        try:
            import winsound
            winsound.PlaySound(self.path(name), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        except Exception:
            pass
