"""
Holi Lite: la mascota. Se mueve, te mira, se posa en las ventanas, se duerme, tiene
emociones propias y reacciona a lo que le haces. Como mascota virtual le da hambre y sueño
una vez al dia, y va ganando confianza (planetas que nacen chicos y crecen).
Todo se maneja desde el menu circular (clic derecho sobre Holi o en el icono de la bandeja).
"""
import datetime as dt
import math
import os
import random
import threading
import time

from PySide6.QtCore import QElapsedTimer, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QColorDialog, QInputDialog, QSystemTrayIcon

from . import autostart
from . import config as C
from . import settings
from .fx import hat_for
from .heart import Heart
from .model import BlobModel
from .needs import PLANET_COLORS, Needs
from .radial import Item, RadialMenu
from .renderer import icon_pixmap
from .sounds import SoundBank
from .system import SystemProbe
from .tips import Tip
from .guard import guard, report as error_report, has_errors
from .update import Updater
from . import __version__
from .window import BlobWindow

SIZES = (("Chico", 22), ("Mediano", 30), ("Grande", 40))
GLOW = "#f2f2f5"                          # resaltado de Comer y Dormir: blanco, como sus ojos


class Controller:
    def __init__(self):
        settings.load()
        self.qs = settings.qsettings()
        self.heart = Heart()
        self.heart.restore(self.qs.value("heart"))
        self.needs = Needs()
        self.needs.restore(self.qs.value("needs"))
        self._idle = 0.0
        self._save_at = time.monotonic()
        self._away = True                 # al abrir cuenta como "volviste" (saludo)
        self._still_t = 0.0
        self._last_cur = None
        self._follow_cd = 10.0
        self._gift_in = random.uniform(*C.GIFT_EVERY)
        self._align_cd = 3.0
        self._menu_open = False           # menu circular abierto: Holi va al centro y crece
        self._menu_return = False         # menu recien cerrado: Holi vuelve a su lugar
        self._menu_home = None
        self._menu_target = None
        self._glide = None                # clic en la bandeja: se desliza al centro de la pantalla
        self._raise_at = 0.0
        self.probe = SystemProbe()
        folder = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "HoliLite", "sounds")
        self.sounds = SoundBank(folder, C.S.get("volume", 35) / 100.0)
        threading.Thread(target=self.sounds.prepare, daemon=True).start()

        self.screens, self.natives = [], []
        self._refresh_screens()
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda *_: self._refresh_screens())
        app.screenRemoved.connect(lambda *_: self._refresh_screens())

        pos = None
        try:
            if self.qs.contains("x") and self.qs.contains("y"):
                pos = (float(self.qs.value("x")), float(self.qs.value("y")))
        except (TypeError, ValueError):
            pos = None
        if pos is None or not self._on_screen(*pos):
            r = QGuiApplication.primaryScreen().availableGeometry()
            pos = (r.right() - C.S["radius"] * 4, r.bottom() - C.S["radius"] * 3)

        self.main = BlobModel(C.S["radius"], *pos)
        self.user_hidden = False
        self.user_paused = False
        self.auto_hidden = False
        self._last_cursor = None
        self._fg_at = 0.0
        self._fg = None
        self._active_hwnd = None
        self._screens_at = time.monotonic()
        self._heart_at = time.monotonic()

        self._build_tray()
        self.win = BlobWindow(self.main, C.S["on_top"])
        self.win.context_menu_requested.connect(lambda _pos: self.open_menu())
        self.win.double_clicked.connect(self._double_click)

        self.clock = QElapsedTimer()
        self.clock.start()
        self.last_ms = self.clock.elapsed()
        self.timer = QTimer()
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(guard(self._tick))            # si un cuadro falla, se salta y sigue
        self.timer.start(int(1000 / C.FPS))

        self.fs_timer = QTimer()
        self.fs_timer.timeout.connect(guard(self._check_fullscreen))
        self.fs_timer.start(1000)
        self.heart_timer = QTimer()
        self.heart_timer.timeout.connect(guard(self._update_heart))
        self.heart_timer.start(1000)

        # guia de la primera vez: cada globito sale una sola vez en la vida. Va antes de
        # _update_needs: si al abrir ya tiene hambre o sueño, ese reclamo usa el globito.
        self.tip = Tip()
        seen = self.qs.value("tips_seen")
        if seen is None and self.needs.trust > 0:          # ya lo conocias (antes de esta version)
            seen = "menu,hunger,sleep,planet"
        self._tips_seen = set(str(seen or "").split(",")) - {""}
        self._work = 0.0                      # minutos seguidos usando el PC (para las pausas)
        QTimer.singleShot(6000, lambda: self._tip_once("menu", "Clic derecho sobre mí: mi menú"))

        # aviso de version nueva (GitHub): al rato de abrir y despues cada 6 horas
        self.updater = Updater()
        self._update_seen = None              # version que ya avisamos
        self._update_error = None
        self._update_at = time.monotonic()
        QTimer.singleShot(15000, self.updater.check)

        self._update_needs(0)                 # planetas listos desde el primer instante
        self._fade(self.win, True, 700)       # aparece de a poco al abrir

    # ================================================================ desvanecidos
    def _fade(self, w, show, dur=260):
        """Muestra u oculta una ventana desvaneciendola (nada aparece ni desaparece de golpe)."""
        old = getattr(w, "_fade_anim", None)
        if old is not None:
            old.stop()
        w._want_visible = show
        if show and not w.isVisible():
            w.setWindowOpacity(0.0)
            w.show()
        elif not show and not w.isVisible():
            return
        anim = QPropertyAnimation(w, b"windowOpacity", w)
        anim.setDuration(dur)
        anim.setStartValue(w.windowOpacity())
        anim.setEndValue(1.0 if show else 0.0)

        def done():
            if not getattr(w, "_want_visible", True):
                w.hide()
                w.setWindowOpacity(1.0)
        anim.finished.connect(done)
        w._fade_anim = anim
        anim.start()

    # ================================================================ Holi
    def _apply_sizes(self):
        self.main.set_radius(C.S["radius"])
        self.win.resize_for_model()
        self.win.place()

    def _double_click(self):
        """Doble clic: se pone cariñoso."""
        m = self.main
        m.feel("love", 1.8)
        m.hop.impulse(-160)
        self.heart.event("pet")

    # ================================================================ pantallas
    def _refresh_screens(self):
        rects, natives = [], []
        for s in QGuiApplication.screens():
            g = s.availableGeometry()
            rects.append((g.x(), g.y(), g.width(), g.height()))
            full = s.geometry()
            dpr = s.devicePixelRatio() or 1.0
            natives.append((full.x(), full.y(), full.width() * dpr, full.height() * dpr, full.x(), full.y(), dpr))
        self.screens = rects or [(0, 0, 1920, 1080)]
        self.natives = natives

    def _on_screen(self, x, y):
        return any(r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3] for r in self.screens)

    def _screen_rect_of(self, x, y):
        for r in self.screens:
            if r[0] <= x <= r[0] + r[2] and r[1] <= y <= r[1] + r[3]:
                return r
        return self.screens[0]

    def _to_logical(self, r):
        if r is None:
            return None
        cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
        for nx, ny, nw, nh, lx, ly, dpr in self.natives:
            if nx <= cx < nx + nw and ny <= cy < ny + nh:
                return (lx + (r[0] - nx) / dpr, ly + (r[1] - ny) / dpr, r[2] / dpr, r[3] / dpr)
        dpr = self.natives[0][6] if self.natives else 1.0
        return (r[0] / dpr, r[1] / dpr, r[2] / dpr, r[3] / dpr)

    # ================================================================ reloj
    def _tick(self):
        now_ms = self.clock.elapsed()
        dt_s = (now_ms - self.last_ms) / 1000.0
        self.last_ms = now_ms
        if self._running():
            self._step(dt_s)
        self._menu_motion(dt_s)                # el menu mueve a Holi aunque este pausado u oculto
        self.win.place()
        self.win.update()
        if self.tip.isVisible():
            self.tip.follow(self.main.x, self.main.y - self.main.R * 1.9)
        if not self._timer_needed():
            self._apply_run_state()            # termino de volver a su lugar estando pausado: para el reloj
            return

    def _step(self, dt_s):
        """Un paso de vida de Holi: lee el PC (mouse, teclado, ventanas) y lo mueve."""
        mono = time.monotonic()
        if mono - self._screens_at > 3:
            self._refresh_screens()
            self._screens_at = mono

        c = QCursor.pos()
        cur = (float(c.x()), float(c.y()))
        idle, new_input = self.probe.input_state()
        self._idle = idle
        self._break_check(dt_s, idle)
        keys = 1 if (new_input and cur == self._last_cursor) else 0
        self._last_cursor = cur

        if mono - self._fg_at > 0.25:
            self._fg_at = mono
            fg = self.probe.perchable_foreground()
            self._fg = (fg[0], self._to_logical(fg[1])) if fg else None
            act = self.probe.foreground_window()
            if act and act[0] != self._active_hwnd:
                first = self._active_hwnd is None
                self._active_hwnd = act[0]
                r = self._to_logical(act[1])
                if not first and r:
                    self.main.glance_at(r[0] + r[2] / 2, r[1] + r[3] / 3)   # mira la ventana que abriste

        now = dt.datetime.now()
        hour = now.hour + now.minute / 60.0
        m = self.main
        m.anchor = self._anchor_pos() if C.S.get("pin") else None
        if self._menu_open or self._menu_return or self._glide:
            m.anchor = (m.x, m.y)                  # quieto mientras se desliza
        if m.dropped is not None:
            self._set_corner_near(*m.dropped)
            m.dropped = None

        m.fg = self._fg
        m.hour = hour
        hwnd = m.perch["hwnd"] if m.perch else m.perch_goal
        m.perch_rect = self._to_logical(self.probe.window_rect(hwnd)) if hwnd else None
        m.update(dt_s, cur, self.screens, idle=idle, keys=keys)
        for name in m.sfx:
            self.play(name)
        for ev in m.events:
            self.heart.event(ev)
        m.sfx.clear()
        m.events.clear()

    def _update_heart(self):
        """Emociones propias: cambian solas con el tiempo y con lo que le haces."""
        mono = time.monotonic()
        step = min(5.0, mono - self._heart_at)
        self._heart_at = mono
        now = dt.datetime.now()
        hour = now.hour + now.minute / 60.0
        m = self.main
        self.heart.update(step, hour, m.since_interaction, m.asleep, m.typing, m.pet)
        feeling = self.heart.feeling(hour)
        m.hat = hat_for(now.date()) if C.S.get("accessories", True) else None
        self._update_needs(step)
        self._unlocked_behaviors(step)
        stage, kind = self.needs.worst()
        if stage >= 3:
            feeling = "molesto"
        elif stage == 2:
            feeling = "triste"
        elif stage == 1 and kind == "sleep":
            feeling = "cansado"
        m.temper = feeling
        m.heart_energy = self.heart.energy
        self._update_tick(mono)
        if mono - self._save_at > 60:
            self._save_at = mono
            self.qs.setValue("needs", self.needs.dump())
            self.qs.setValue("heart", self.heart.dump())

    # ================================================================ mascota virtual
    def _running(self):
        return not self.user_hidden and not self.auto_hidden and not self.user_paused

    def _timer_needed(self):
        """El reloj corre mientras Holi vive, o mientras el menu lo mueve (aunque este pausado u oculto)."""
        return self._running() or self._menu_open or self._menu_return or bool(self._glide)

    def _update_needs(self, step):
        m = self.main
        n = self.needs
        if self._running():
            n.update(step, present=self._idle < 300)
        for ev in n.take_events():
            if ev == "woke":
                m.end_nap()
            elif ev == "reclaim" and self._running() and not n.napping():
                stage, kind = n.worst()
                if stage:
                    m.reclaim(kind, stage)
                    if kind == "hunger":
                        self._tip_once("hunger", "Tengo hambre.\nClic derecho y Comer")
                    else:
                        self._tip_once("sleep", "Tengo sueño.\nClic derecho y Dormir")
            elif ev == "star":
                if m.orbit is not None:
                    m.orbit["new"] = 2.5
                if n.visible_planets() == 1 and n.planets_earned() == 0:
                    QTimer.singleShot(1500, lambda: self._tip_once(
                        "planet", "¡Nació mi primer planeta!\nCrece mientras pasamos tiempo juntos"))
                m.happy.target = 1.0
                m.happy_time = 1.2
            elif ev == "moon":
                if m.orbit is not None:
                    m.orbit["moon_new"] = 2.0
                m.celebrate()
                if self.tray:
                    self.tray.showMessage(self.name(), "Un planeta de %s ganó su luna." % self.name(),
                                          QSystemTrayIcon.MessageIcon.Information, 6000)
            elif ev == "planet":
                m.celebrate()
                done = n.planets_earned()
                learned = C.UNLOCK_TEXT.get(C.UNLOCKS[done - 1], "") if 0 < done <= len(C.UNLOCKS) else ""
                if done >= len(C.UNLOCKS):
                    QTimer.singleShot(2500, m.align)
                if self.tray:
                    learned = learned.replace("Holi", self.name())
                    self.tray.showMessage(self.name(), "Un planeta de %s terminó de crecer. " % self.name() + learned,
                                          QSystemTrayIcon.MessageIcon.Information, 7000)
        if n.napping() and not m.napping:
            m.start_nap()
        elif not n.napping() and m.napping:
            m.end_nap()
        stage, kind = n.worst()
        m.need_target = {0: (0.0, 0.0), 1: (0.3, 0.0), 2: (1.0, 0.0), 3: (0.3, 1.0)}[stage]
        self._sync_orbit()

    def _sync_orbit(self):
        m, n = self.main, self.needs
        old = m.orbit or {}
        moons = n.moons()
        newest = moons - 1 if old.get("moon_new", 0.0) > 0 else -1
        planets = [(c, s, ("new" if i == newest else True) if i < moons else False)
                   for i, (c, s) in enumerate(zip(n.planet_colors, n.planet_sizes()))]
        m.orbit = {"planets": planets, "new": old.get("new", 0.0), "moon_new": old.get("moon_new", 0.0)}

    def _unlocked(self):
        return set(C.UNLOCKS[:self.needs.planets_earned()])

    def _unlocked_behaviors(self, step):
        """Lo que Holi aprendio con la confianza (un desbloqueo por planeta que termino de crecer)."""
        m = self.main
        un = self._unlocked()
        m.unlocks = un
        if not self._running() or self._menu_open or self._menu_return:
            return
        fast = C.FAST_FACTOR if C.S.get("fast_mode") else 1.0
        idle = self._idle

        # 1. saludo al volver
        if idle > C.GREET_AWAY:
            self._away = True
        elif self._away and idle < 2.0:
            self._away = False
            if "greet" in un:
                m.greet()

        # 2. te sigue: mouse quieto lejos de el un rato -> va hacia ti
        c = QCursor.pos()
        cur = (float(c.x()), float(c.y()))
        self._still_t = self._still_t + step if cur == self._last_cur else 0.0
        self._last_cur = cur
        self._follow_cd = max(0.0, self._follow_cd - step)
        far = math.hypot(cur[0] - m.x, cur[1] - m.y) > C.FOLLOW_FAR
        if ("follow" in un and far and self._still_t > C.FOLLOW_STILL and self._follow_cd <= 0
                and m.anchor is None and not m.asleep and m.mode in (BlobModel.IDLE, BlobModel.WANDER, BlobModel.PERCH)):
            sx, sy, sw, sh = self._screen_rect_of(*cur)
            side = -1 if m.x < cur[0] else 1
            tx = min(max(cur[0] + side * 170, sx + m.R * 2), sx + sw - m.R * 2)
            ty = min(max(cur[1] + 40, sy + m.R * 2), sy + sh - m.R * 2)
            m.perch = m.perch_goal = None
            m._go((tx, ty), 240.0)
            m.feel("excited", 1.0)
            self._follow_cd = C.FOLLOW_COOLDOWN

        stage, _ = self.needs.worst()
        # 4. regalo de vez en cuando (solo si esta bien atendido)
        if "gift" in un and idle < 300 and stage == 0:
            self._gift_in -= step / 60.0 * fast
            if self._gift_in <= 0:
                self._gift_in = random.uniform(*C.GIFT_EVERY)
                m.give_gift()

        # 5. planetas alineados cuando esta muy contento
        self._align_cd = max(0.0, self._align_cd - step / 60.0 * fast)
        if ("align" in un and self._align_cd <= 0 and m.temper in ("feliz", "carinoso")
                and not m.asleep and random.random() < step / 90.0):
            m.align()
            self._align_cd = C.ALIGN_COOLDOWN

    def feed(self):
        m = self.main
        if self.needs.feed():
            m.fx.want_t = 0.0
            m.fx.emit("snack", m.R)
            self.heart.event("pet")
            QTimer.singleShot(600, m.eat)
        else:
            m.refuse()

    def send_to_sleep(self):
        m = self.main
        if self.needs.put_to_sleep():
            m.fx.want_t = 0.0
            m.start_nap()
        else:
            m.refuse()

    def _need_text(self):
        n = self.needs
        if n.napping():
            return self.name() + " está durmiendo su siesta"
        wants = [label for kind, label in (("hunger", "hambre"), ("sleep", "sueño")) if n.stage(kind)]
        if not wants:
            return self.name() + " está bien"
        stage, _ = n.worst()
        return self.name() + " tiene " + " y ".join(wants) + {2: " (está triste)", 3: " (está enojado)"}.get(stage, "")

    def _trust_text(self):
        n = self.needs
        p, s = n.planets_earned(), n.stars()
        if n.maxed():
            lunas = n.moons()
            if n.complete():
                txt = "Confianza · al máximo: %d planetas con su luna" % p
            elif lunas:
                txt = "Confianza · %d luna%s, la siguiente al %d%%" % (lunas, "" if lunas == 1 else "s", n.moon_progress() * 100)
            else:
                txt = "Confianza · 5 planetas, la primera luna al %d%%" % (n.moon_progress() * 100)
            return txt + " · %d día%s juntos" % (n.days, "" if n.days == 1 else "s")
        if s == 0:
            txt = "Confianza · está por nacer un planeta" if p else "Confianza · aún sin planetas"
        else:
            txt = "Confianza · planeta %d creciendo (%d de %d)" % (p + 1, s, C.GROW_STAGES)
        if p:
            txt += ", %d grande%s" % (p, "" if p == 1 else "s")
        return txt

    def _set_planet_color(self, i, hexc):
        if 0 <= i < len(self.needs.planet_colors):
            self.needs.planet_colors[i] = hexc
            self.qs.setValue("needs", self.needs.dump())
            self._sync_orbit()                    # el planeta cambia de color al tiro
            self.main.happy.target = 1.0
            self.main.happy_time = 1.2

    def _pick_planet_color(self, i):
        c = QColorDialog.getColor(QColor(self.needs.planet_colors[i]), None, "Color del planeta %d" % (i + 1))
        if c.isValid():
            self._set_planet_color(i, c.name())

    # ================================================================ esquina fija
    def _anchor_pos(self, corner=None):
        corner = corner or C.S.get("pin_corner", "br")
        sx, sy, sw, sh = self._screen_rect_of(self.main.x, self.main.y)
        R = self.main.R
        mx, my = R * 2.4, R * 1.9
        x = sx + mx if corner[1] == "l" else sx + sw - mx
        y = sy + my if corner[0] == "t" else sy + sh - my
        return (x, y)

    def _set_corner_near(self, x, y):
        best = min(("tl", "tr", "bl", "br"),
                   key=lambda c: math.hypot(self._anchor_pos(c)[0] - x, self._anchor_pos(c)[1] - y))
        C.S["pin_corner"] = best
        settings.save()

    def set_pin(self, on):
        C.S["pin"] = bool(on)
        settings.save()
        if on:
            self.main.perch = self.main.perch_goal = None
            self.main.squash.impulse(4.0)

    # ================================================================ sonidos
    def play(self, name):
        if C.S.get("voice", True):
            self.sounds.play(name)

    # ================================================================ visibilidad
    def _apply_run_state(self):
        w = self.win
        visible = not self.user_hidden and not self.auto_hidden
        want = getattr(w, "_want_visible", w.isVisible())
        if visible and (not w.isVisible() or not want):
            self._fade(w, True)
        elif not visible and w.isVisible() and want:
            self._fade(w, False)
        w.paused = not self._running()
        need = self._timer_needed()
        if need and not self.timer.isActive():
            self.last_ms = self.clock.elapsed()
            self.timer.start(int(1000 / C.FPS))
        elif not need and self.timer.isActive():
            self.timer.stop()
        w.update()

    def _check_fullscreen(self):
        fs = False
        if C.S["hide_fullscreen"] and not self.user_hidden:
            try:
                fs = self.probe.fullscreen_on_monitor_of(int(self.win.winId()))
            except Exception:
                fs = False
        if fs != self.auto_hidden:
            self.auto_hidden = fs
            self._apply_run_state()

    def hide_blob(self):
        """Ocultar desde el menu. Vuelve con clic en el icono de la bandeja (o abriendo el menu desde ahi)."""
        self.user_hidden = True
        self._apply_run_state()

    def set_paused(self, paused):
        self.user_paused = paused
        self._apply_run_state()

    def show_blob(self):
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        self.main.spin_planets()
        if self.user_hidden or not self.win.isVisible():
            self.main.bring_to(g.center().x(), g.center().y())      # estaba oculto: aparece ahi (con fundido)
        elif not self._menu_open:
            self._glide = (g.center().x(), g.center().y())           # visible: se desliza hasta ahi
        self.user_hidden = False
        self._apply_run_state()

    # ================================================================ bandeja
    def _build_tray(self):
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(QIcon(icon_pixmap(64)))
            self.tray.setToolTip(self.name())
            self.tray.activated.connect(self._tray_activated)
            self.tray.show()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_blob()
        elif reason == QSystemTrayIcon.Context:
            self.open_menu()

    # ================================================================ menu circular
    # ================================================================ nombre
    def name(self):
        return (C.S.get("name") or "").strip() or "Holi"

    def _rename(self):
        """Opciones > Nombre (el instalador lo pregunta la primera vez)."""
        text, ok = QInputDialog.getText(None, C.APP_NAME, "¿Cómo se llama tu mascota?", text=self.name())
        text = " ".join(text.split())[:20]
        if ok and text:
            C.S["name"] = text
            settings.save()
            if self.tray:
                self.tray.setToolTip(text)
            self.main.happy.target = 1.0
            self.main.happy_time = 1.4
            self.play("tada")

    # ================================================================ version nueva
    def _update_tick(self, mono):
        if mono - self._update_at > 6 * 3600:
            self._update_at = mono
            self.updater.check()
        new = self.updater.latest
        if new and new["version"] != self._update_seen:
            self._update_seen = new["version"]
            text = "Hay una versión nueva de Holi (%s).\nOpciones > Actualizar" % new["version"]
            if self.tray:
                self.tray.showMessage(self.name(), text.replace("\n", ". "), QSystemTrayIcon.MessageIcon.Information, 8000)
            self._say(text, 8.0)
        if self._update_error:
            self._say("No pude actualizar:\n" + self._update_error[:60], 6.0)
            self._update_error = None

    def _do_update(self):
        self._say("Bajando la versión nueva...\nme cierro y vuelvo solo", 10.0)
        self.updater.install(lambda msg: setattr(self, "_update_error", msg))

    def _report(self):
        """Copia version y ultimos errores al portapapeles, listo para pegar en el chat."""
        QApplication.clipboard().setText(error_report())
        if has_errors():
            self._say("Copié el detalle del problema.\nPégalo en el chat para revisarlo.", 6.0)
        else:
            self._say("No hay errores anotados.\nIgual copié la versión.", 5.0)

    # ================================================================ globitos
    def _tip_once(self, key, text):
        """Guia de la primera vez: cada globito sale una sola vez."""
        if key in self._tips_seen or not self._running() or self._menu_open:
            return
        self._tips_seen.add(key)
        self.qs.setValue("tips_seen", ",".join(sorted(self._tips_seen)))
        self._say(text)

    def _say(self, text, secs=7.0):
        self.tip.say(text, secs)
        self.tip.follow(self.main.x, self.main.y - self.main.R * 1.9)

    def _break_check(self, dt_s, idle):
        """Pausas (opcional): despues de BREAK_AFTER minutos seguidos usando el PC, se despereza y te mira."""
        if idle >= C.BREAK_RESET * 60:
            self._work = 0.0                  # ya hiciste una pausa
            return
        if idle < 60:
            self._work += dt_s / 60.0
        if C.S.get("breaks") and self._work >= C.BREAK_AFTER and not self._menu_open and not self.needs.napping():
            self._work = 0.0
            c = QCursor.pos()
            self.main.suggest_break(c.x(), c.y())
            self._say("Llevas rato sin parar.\n¿Una pausa?", 8.0)

    def open_menu(self):
        """El menu se abre alrededor del Holi real: Holi se desliza al centro de su pantalla y crece."""
        if not hasattr(self, "radial"):
            self.radial = RadialMenu(self._radial_page, lambda: (self._need_text(), self._trust_text()),
                                     self._menu_closing)
        m = self.main
        scr = QGuiApplication.screenAt(QPoint(int(m.x), int(m.y))) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        cx, cy = g.center().x(), g.center().y()
        if not self._menu_open and not self._menu_return:
            self._menu_home = (m.x, m.y)
        self._menu_open = True
        self._menu_return = False
        self._glide = None
        self._menu_target = (cx, cy)
        self.user_hidden = False
        self._apply_run_state()                   # aparece si estaba oculto y el reloj corre aunque este pausado
        if m.asleep and not m.napping:
            m._wake()
        m.spin_planets()
        m.perch = m.perch_goal = None
        self.tip.dismiss()
        self.radial.open_around(cx, cy, (g.x(), g.y(), g.width(), g.height()))
        self._raise_holi()
        QTimer.singleShot(60, self._raise_holi)

    def _raise_holi(self):
        self.win.raise_()

    def _menu_closing(self):
        self._menu_open = False
        self._menu_return = True

    def _menu_radius(self):
        base = float(C.S["radius"])
        return max(base, min(base * 1.5, 46.0))

    def _menu_motion(self, dt):
        """Desliza y agranda a Holi hacia el centro (menu abierto) y de vuelta (menu cerrado)."""
        m = self.main
        base = float(C.S["radius"])
        if self._menu_open:
            tx, ty = self._menu_target
            tR = self._menu_radius()
            mono = time.monotonic()
            if mono - self._raise_at > 0.4:           # que Holi quede sobre el menu
                self._raise_at = mono
                self._raise_holi()
        elif self._menu_return:
            tx, ty = self._anchor_pos() if C.S.get("pin") else self._menu_home
            tR = base
        elif self._glide:
            tx, ty = self._glide
            tR = base
        else:
            return
        k = 1 - math.exp(-dt * 9.0)
        m.x += (tx - m.x) * k
        m.y += (ty - m.y) * k
        m.vx = m.vy = 0.0
        if m.mode not in (BlobModel.IDLE,):
            m.mode = BlobModel.IDLE
        m.target = None
        m.decide_in = max(m.decide_in, 3.0)
        r = m.R + (tR - m.R) * k
        if abs(tR - r) < 0.05:
            r = tR                                # llega justo a su tamano (antes quedaba a medio camino y no terminaba)
        if r != m.R:
            m.set_radius(r)
            self.win.resize_for_model()
        if not self._menu_open and math.hypot(tx - m.x, ty - m.y) < 1.0 and m.R == tR:
            self._menu_return = False
            self._glide = None

    def _toggle_item(self, label, icon, key, after=None, short=None):
        def flip():
            C.S[key] = not C.S.get(key)
            settings.save()
            if after:
                after()
        return Item(label, icon, flip, checked=bool(C.S.get(key)), keep_open=True, short=short)

    def _radial_page(self, name):
        n = self.needs
        if name == "main":
            napping = n.napping()
            return self.name(), [
                Item("Dar comida", "food", self.feed, short="Comer",
                     state="¡tiene hambre!" if n.hungry else "ahora no tiene hambre",
                     glow=GLOW if n.hungry else None),
                Item("Mandar a dormir", "sleep", self.send_to_sleep, short="Dormir",
                     state="durmiendo" if napping else ("¡tiene sueño!" if n.sleepy else "ahora no tiene sueño"),
                     glow=GLOW if (n.sleepy and not napping) else None),
                Item("Planetas", "planets", page="planets", short="Planetas",
                     state="%d de %d · cambiar colores" % (n.visible_planets(), C.MAX_PLANETS)),
                Item("Ocultar a " + self.name(), "hide", self.hide_blob, short="Ocultar",
                     state="vuelve con clic en la bandeja"),
                Item("Pausar", "pause", lambda: self.set_paused(not self.user_paused), short="Pausar",
                     checked=self.user_paused, keep_open=True, state="se queda quieto" if self.user_paused else "se mueve libre"),
                Item("Opciones", "options", page="options", short="Opciones",
                     state="esquina, tamaño, salir y más"),
            ]
        if name == "planets":
            done = n.planets_earned()
            items = []
            for i, col in enumerate(n.planet_colors):
                items.append(Item("Planeta %d" % (i + 1), "color", page="pcolor:%d" % i, color=col, short="Planeta %d" % (i + 1),
                                  state="creciendo" if i >= done else "grande"))
            return ("Planetas" if items else "Todavía no nace ninguno"), items
        if name.startswith("pcolor:"):
            i = int(name.split(":")[1])
            if i >= len(n.planet_colors):
                return "Planetas", []
            current = n.planet_colors[i].lower()
            items = []
            for label, hexc in PLANET_COLORS:
                sel = current == hexc.lower()
                items.append(Item(label, "color", lambda h=hexc, ii=i: self._set_planet_color(ii, h), color=hexc,
                                  checked=True if sel else None, keep_open=True, state="color actual" if sel else None))
            other = lambda ii=i: self._pick_planet_color(ii)
            if any(current == h.lower() for _, h in PLANET_COLORS):
                items.append(Item("Otro color...", "custom", other, short="Otro"))
            else:                                  # color elegido a mano: se muestra marcado en "Otro"
                items.append(Item("Otro color...", "color", other, color=current, checked=True, short="Otro",
                                  state="color actual"))
            return "Color del planeta %d" % (i + 1), items
        if name == "size":
            icons = {"Chico": "small", "Mediano": "medium", "Grande": "large"}
            return "Tamaño", [Item(label, icons[label], lambda rr=r: self._set_size(rr),
                                   checked=C.S["radius"] == r, keep_open=True) for label, r in SIZES]
        if name == "options":
            items = []
            if self.updater.latest:
                items.append(Item("Actualizar a la versión " + self.updater.latest["version"], "update", self._do_update,
                                  short="Actualizar", glow=GLOW, state="baja e instala, tus planetas se mantienen"))
            items += [
                self._toggle_item("Sonidos", "sound", "voice", short="Sonidos"),
                self._toggle_item("Recordarme pausas si llevo mucho rato sin parar", "break", "breaks", short="Pausas"),
                self._toggle_item("Gorritos según la fecha", "hat", "accessories", short="Gorritos"),
                self._toggle_item("Posarse sobre las ventanas", "perch", "perch", short="Posarse"),
                self._toggle_item("Ánimo según la hora del día", "clock", "time_mood", short="Ánimo por hora"),
                self._toggle_item("Ocultarse con juegos y videos a pantalla completa", "fullscreen", "hide_fullscreen",
                                  self._check_fullscreen, short="Pantalla completa"),
                self._toggle_item("Siempre visible sobre las ventanas", "ontop", "on_top", self._apply_on_top,
                                  short="Siempre visible"),
            ]
            if autostart.supported():
                items.append(Item("Abrir con Windows", "power", lambda: autostart.set_enabled(not autostart.is_enabled()),
                                  checked=autostart.is_enabled(), keep_open=True, short="Con Windows"))
            items += [
                Item("Fijo en una esquina", "pin", lambda: self.set_pin(not C.S.get("pin")), short="Esquina",
                     checked=bool(C.S.get("pin")), keep_open=True),
                Item("Tamaño", "size", page="size", short="Tamaño"),
                Item("Cambiarle el nombre", "name", self._rename, short="Nombre", state=self.name()),
                Item("Reportar un problema", "report", self._report, short="Reportar",
                     state="copia el detalle para pegarlo" if has_errors() else "no hay errores anotados"),
                Item("Cerrar " + self.name(), "exit", QApplication.instance().quit, short="Salir"),
            ]
            return "Opciones · versión " + __version__, items
        return "", []

    def _set_size(self, r):
        C.S["radius"] = r
        settings.save()
        if not (self._menu_open or self._menu_return):
            self._apply_sizes()

    def _apply_on_top(self):
        self.win.set_on_top(C.S["on_top"])

    # ================================================================ salida
    def save(self):
        self.qs.setValue("heart", self.heart.dump())
        self.qs.setValue("needs", self.needs.dump())
        self.qs.setValue("x", self.main.x)
        self.qs.setValue("y", self.main.y)
        settings.save()
