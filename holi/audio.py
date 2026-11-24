"""Cuanto suena el PC ahora (0..1), para que Holi baile.

Lee el medidor de pico de la salida de audio por defecto de Windows (el mismo que mueve la barrita
verde del mezclador de volumen). No graba ni escucha nada: solo pregunta "que tan fuerte suena".
Si algo falla (no es Windows, no hay comtypes, no hay parlantes) devuelve 0 y no molesta mas.
"""
import sys
import time

_meter = None
_failed_at = None
RETRY = 30.0          # si fallo (por ejemplo, cambiaste de audifonos), reintenta cada 30 s


def _open():
    import comtypes
    from comtypes import GUID, COMMETHOD, HRESULT, IUnknown
    from ctypes import POINTER, c_float, c_uint, c_void_p

    class IAudioMeterInformation(IUnknown):
        _iid_ = GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
        _methods_ = [COMMETHOD([], HRESULT, "GetPeakValue", (["out"], POINTER(c_float), "peak"))]

    class IMMDevice(IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [COMMETHOD([], HRESULT, "Activate",
                               (["in"], POINTER(GUID), "iid"), (["in"], c_uint, "ctx"),
                               (["in"], c_void_p, "params"), (["out"], POINTER(POINTER(IUnknown)), "out"))]

    class IMMDeviceEnumerator(IUnknown):
        _iid_ = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
        _methods_ = [
            COMMETHOD([], HRESULT, "EnumAudioEndpoints"),
            COMMETHOD([], HRESULT, "GetDefaultAudioEndpoint",
                      (["in"], c_uint, "flow"), (["in"], c_uint, "role"),
                      (["out"], POINTER(POINTER(IMMDevice)), "dev")),
        ]

    try:
        comtypes.CoInitialize()                              # Qt ya lo inicio en este hilo: no pasa nada
    except OSError:
        pass
    enum = comtypes.CoCreateInstance(GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}"),
                                     IMMDeviceEnumerator, comtypes.CLSCTX_ALL)
    dev = enum.GetDefaultAudioEndpoint(0, 0)                 # salida, consola
    unk = dev.Activate(IAudioMeterInformation._iid_, 23, None)
    return unk.QueryInterface(IAudioMeterInformation)


def level():
    """Pico actual de lo que suena, 0..1. Nunca lanza errores."""
    global _meter, _failed_at
    if sys.platform != "win32":
        return 0.0
    if _meter is None:
        if _failed_at is not None and time.monotonic() - _failed_at < RETRY:
            return 0.0
        try:
            _meter = _open()
            _failed_at = None
        except Exception:
            _failed_at = time.monotonic()
            return 0.0
    try:
        return max(0.0, min(1.0, float(_meter.GetPeakValue())))
    except Exception:
        _meter = None                                        # se desconecto el dispositivo: reabrir luego
        _failed_at = time.monotonic()
        return 0.0
