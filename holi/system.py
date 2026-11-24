"""
Lecturas del sistema (solo Windows; en otros sistemas devuelve valores neutros):
- cuanto tiempo lleva el PC sin uso y si hubo una pulsacion nueva (para detectar tipeo)
- si hay una app en pantalla completa en el monitor del blob
No instala ganchos de teclado ni lee que teclas se presionan: solo sabe que hubo actividad.
"""
import os
import sys

IS_WIN = sys.platform.startswith("win")

if IS_WIN:
    import ctypes
    from ctypes import wintypes as wt

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

    user32.GetForegroundWindow.restype = wt.HWND
    user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user32.MonitorFromWindow.restype = wt.HMONITOR
    user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
    user32.GetMonitorInfoW.argtypes = [wt.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    kernel32.GetTickCount.restype = wt.DWORD
    user32.IsWindow.argtypes = [wt.HWND]
    user32.IsWindowVisible.argtypes = [wt.HWND]
    user32.IsIconic.argtypes = [wt.HWND]
    user32.IsZoomed.argtypes = [wt.HWND]
    try:
        dwmapi = ctypes.windll.dwmapi
        dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]
    except Exception:
        dwmapi = None

SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


class SystemProbe:
    def __init__(self):
        self._last_input = None
        self._pid = os.getpid()

    def input_state(self):
        """Devuelve (segundos_sin_uso, hubo_input_nuevo)."""
        if not IS_WIN:
            return 0.0, False
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0, False
        now = kernel32.GetTickCount()
        idle = ((now - info.dwTime) & 0xFFFFFFFF) / 1000.0
        new = self._last_input is not None and info.dwTime != self._last_input
        self._last_input = info.dwTime
        return idle, new

    def fullscreen_on_monitor_of(self, own_hwnd):
        """True si la ventana activa ocupa todo el monitor donde esta el blob (juego, video, presentacion)."""
        if not IS_WIN:
            return False
        try:
            fg = user32.GetForegroundWindow()
            if not fg:
                return False
            pid = wt.DWORD()
            user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            if pid.value == self._pid:
                return False
            buf = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(fg, buf, 64)
            if buf.value in SHELL_CLASSES:
                return False
            mon = user32.MonitorFromWindow(fg, 2)
            if not mon or mon != user32.MonitorFromWindow(wt.HWND(own_hwnd), 2):
                return False
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(mon, ctypes.byref(mi))
            r = wt.RECT()
            user32.GetWindowRect(fg, ctypes.byref(r))
            m = mi.rcMonitor
            return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom
        except Exception:
            return False

    # ------------------------------------------------------------ ventanas
    def _window_ok(self, hwnd):
        if not hwnd or not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
            return False
        if user32.IsIconic(hwnd):
            return False
        pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == self._pid:
            return False
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        return buf.value not in SHELL_CLASSES

    def window_rect(self, hwnd):
        """Rectangulo visible de una ventana en pixeles fisicos (x, y, w, h), o None."""
        if not IS_WIN:
            return None
        try:
            hwnd = wt.HWND(hwnd)
            if not self._window_ok(hwnd):
                return None
            r = wt.RECT()
            ok = False
            if dwmapi is not None:        # DWMWA_EXTENDED_FRAME_BOUNDS: sin bordes invisibles
                ok = dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) == 0
            if not ok:
                user32.GetWindowRect(hwnd, ctypes.byref(r))
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        except Exception:
            return None

    def perchable_foreground(self):
        """(hwnd, rect) de la ventana activa si sirve para posarse encima (no maximizada)."""
        if not IS_WIN:
            return None
        try:
            fg = user32.GetForegroundWindow()
            if not fg or user32.IsZoomed(fg):
                return None
            rect = self.window_rect(fg)
            if not rect or rect[2] < 220 or rect[3] < 120:
                return None
            return int(fg), rect
        except Exception:
            return None

    def foreground_window(self):
        """(hwnd, rect) de la ventana activa (cualquiera menos el escritorio, la barra y Holi)."""
        if not IS_WIN:
            return None
        try:
            fg = user32.GetForegroundWindow()
            if not fg:
                return None
            rect = self.window_rect(fg)
            if not rect or rect[2] < 80 or rect[3] < 60:
                return None
            return int(fg), rect
        except Exception:
            return None
