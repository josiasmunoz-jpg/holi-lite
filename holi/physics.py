"""Herramientas de fisica simple: resortes amortiguados y suavizado."""
import math


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def approach(current, target, rate, dt):
    """Acerca current a target de forma exponencial (independiente de los fps)."""
    return current + (target - current) * (1.0 - math.exp(-rate * dt))


class Spring:
    """Resorte amortiguado 1D. k = rigidez, c = amortiguacion."""

    def __init__(self, value=0.0, k=120.0, c=12.0):
        self.x = value
        self.v = 0.0
        self.target = value
        self.k = k
        self.c = c

    def step(self, dt):
        a = -self.k * (self.x - self.target) - self.c * self.v
        self.v += a * dt
        self.x += self.v * dt
        return self.x

    def impulse(self, dv):
        self.v += dv


class Spring2:
    """Resorte amortiguado 2D (dos resortes independientes)."""

    def __init__(self, k=120.0, c=12.0):
        self.a = Spring(0.0, k, c)
        self.b = Spring(0.0, k, c)

    def set_target(self, x, y):
        self.a.target, self.b.target = x, y

    def step(self, dt):
        return self.a.step(dt), self.b.step(dt)

    @property
    def value(self):
        return self.a.x, self.b.x

    def energy(self):
        return abs(self.a.v) + abs(self.b.v) + abs(self.a.x - self.a.target) + abs(self.b.x - self.b.target)
