"""Configuracion de Holi Lite (solo la mascota). DEFAULTS se guardan en el registro del usuario."""

APP_NAME = "Holi Lite"
GITHUB_REPO = "josiasmunoz-jpg/holi-lite"   # donde se publican las versiones (aviso de version nueva)
ORG_NAME = "Holi"
SINGLE_INSTANCE_KEY = "HoliLite-single-instance"

DEFAULTS = {
    "radius": 30,                # tamano (px)
    "body_color": "#101012",
    "eye_color": "#ffffff",
    "speed": 1.0,
    "pc_sleep_min": 2.0,         # minutos sin usar el PC para dormirse
    "fade_alpha": 0.35,          # opacidad cuando estorba
    "max_yaw": 0.6,
    "perch": True,               # posarse sobre ventanas
    "time_mood": True,           # animo segun la hora
    "hide_fullscreen": True,
    "on_top": True,
    "name": "Holi",              # como se llama (se elige al instalar o en Opciones > Nombre)
    "voice": True,               # ruiditos
    "breaks": False,             # recordarte pausas si llevas mucho rato sin parar (apagado de fabrica)
    "volume": 35,
    "pin": False,
    "pin_corner": "br",
    "accessories": True,         # gorro navideño y otros segun la fecha
    "fast_mode": False,          # modo prueba: todo pasa 60 veces mas rapido (quitar antes de publicar)
}
S = dict(DEFAULTS)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------- diseno
RIM_ALPHA = 22
SHADOW_ALPHA = 46

EYE_HEIGHT = 0.60               # ojos circulares
EYE_WIDTH = 0.60
EYE_SPREAD = 0.55
FACE_YAW = 0.35
FACE_PITCH = 0.30

WANDER_SPEED = (40.0, 75.0)
WANDER_DISTANCE = (120.0, 380.0)
IDLE_TIME = (4.0, 10.0)
CURSOR_NEAR = 240.0
SLEEPY_AFTER = 45.0
TYPING_RATE = 5.0
GRAVITY = 1700.0

# ---------------------------------------------------------------- mascota virtual
# Todos los tiempos en minutos de uso con Holi abierto (el PC apagado no cuenta).
HUNGRY_AFTER_USE = 60.0          # le da hambre 1 vez al dia, despues de 1 hora de uso
SLEEPY_AFTER_USE = 180.0         # le da sueño 1 vez al dia, despues de 3 horas de uso
NEED_SAD_AFTER = 45.0            # sin atender: triste a los 45 min
NEED_ANGRY_AFTER = 120.0         # sin atender: enojado a las 2 horas
RECLAIM_EVERY = 25.0             # reclama como maximo cada 25 min
NAP_SECONDS = 240.0              # la siesta dura 4 minutos reales y despierta solo

TRUST_PER_MINUTE = 1.0           # confianza por minuto juntos (con el PC en uso)
TRUST_CARE = 30.0                # bonus por atenderlo a tiempo
TRUST_CARE_LATE = 10.0           # bonus si ya estaba triste o enojado
STAR_POINTS = 150.0              # puntos por etapa de crecimiento del primer planeta (~2 dias de uso normal)
PLANET_GROWTH = 2.0              # cada planeta cuesta mas: 1x, 3x, 5x, 7x, 9x
GROW_STAGES = 5                  # etapas: nace chiquitito y crece hasta su tamano final
MAX_PLANETS = 5
MOON_POINTS = 2400.0             # despues de los 5 planetas: cada planeta gana una luna (~40 horas juntos cada una)
PLANET_SIZES = (0.05, 0.065, 0.08, 0.10, 0.125)   # radio por etapa, relativo a Holi
PLANET_SIZE_VAR = (1.0, 0.85, 1.15, 0.9, 1.05)   # cada planeta termina de un tamano distinto
ORBIT_FIRST = 1.3                # radio de la orbita del primer planeta (veces el radio de Holi)
ORBIT_GAP = 0.18                 # separacion entre orbitas
ORBIT_SPEED = 0.5                # rad/s de la orbita mas interna; las de afuera giran mas lento (Kepler)

# desbloqueos: cada planeta que termina de crecer le ensena algo nuevo a Holi (en este orden)
UNLOCKS = ("greet", "follow", "cuddle", "gift", "align")
UNLOCK_TEXT = {
    "greet": "Ahora Holi te saluda cuando vuelves al PC.",
    "follow": "Ahora Holi te sigue cuando dejas el mouse en otra parte de la pantalla.",
    "cuddle": "Ahora Holi se acurruca junto al cursor si lo dejas quieto cerca de él.",
    "gift": "Ahora Holi te trae una estrellita de regalo de vez en cuando.",
    "align": "Holi llegó al máximo: cuando está muy contento, sus planetas se alinean y brillan.",
}
GREET_AWAY = 300.0               # segundos sin usar el PC para que cuente como "volver"
FOLLOW_STILL = 3.0               # segundos con el mouse quieto lejos para que vaya hacia ti
FOLLOW_FAR = 600.0               # distancia (px) a partir de la cual te sigue
FOLLOW_COOLDOWN = 90.0
CUDDLE_STILL = 2.5               # segundos con el cursor quieto cerca para acurrucarse
CUDDLE_COOLDOWN = 45.0
GIFT_EVERY = (40.0, 80.0)        # minutos de uso entre regalos
ALIGN_COOLDOWN = 20.0            # minutos minimo entre alineaciones de planetas
ALIGN_SECONDS = 5.0

FAST_FACTOR = 60.0               # modo prueba: 1 minuto pasa en 1 segundo
FAST_DAY_SECONDS = 600.0         # modo prueba: un "dia" dura 10 minutos

BREAK_AFTER = 50.0               # minutos seguidos usando el PC antes de sugerir una pausa
BREAK_RESET = 5.0                # minutos sin usar el PC que cuentan como pausa
FPS = 60                         # siempre 60 cuadros por segundo (se detiene solo si esta oculto o hay pantalla completa)
