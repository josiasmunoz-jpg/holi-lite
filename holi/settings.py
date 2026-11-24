"""Carga y guarda los ajustes del usuario."""
from PySide6.QtCore import QSettings

from . import config as C


def qsettings():
    return QSettings(C.ORG_NAME, C.APP_NAME)


def _cast(raw, default):
    if isinstance(default, bool):
        return str(raw).lower() in ("true", "1", "yes")
    if isinstance(default, int):
        return int(float(raw))
    if isinstance(default, float):
        return float(raw)
    return str(raw)


def load():
    qs = qsettings()
    for k, default in C.DEFAULTS.items():
        raw = qs.value(k)
        if raw is None:
            continue
        try:
            C.S[k] = _cast(raw, default)
        except (TypeError, ValueError):
            C.S[k] = default


def save():
    qs = qsettings()
    for k, v in C.S.items():
        qs.setValue(k, v)
    qs.sync()
