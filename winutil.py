"""Windows'a özel yardımcılar: VLC penceresini bulma, odak çalmayan pencereler."""
import ctypes
import os
from collections import namedtuple
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]

class MONITORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT),
                ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]


user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]

MONITOR_DEFAULTTONEAREST = 2
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
LWA_COLORKEY, LWA_ALPHA = 0x1, 0x2
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x2, 0x4, 0x10, 0x20

OWN_PID = os.getpid()

VlcWindow = namedtuple('VlcWindow', 'pid rect bar_top')  # rect None => simge durumunda
# bar_top: tam ekranda görünen kontrol çubuğunun üst kenarı (yoksa None)


def enable_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def _title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def _pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def _windows(pred):
    found = []

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd) and pred(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def find_vlc():
    """Takip edilecek VLC penceresi. Tam ekranda video penceresi en büyüğü olur."""
    mains = _windows(lambda h: _title(h).endswith('VLC media player'))
    if not mains:
        return None
    pid = _pid(mains[0])
    if user32.IsIconic(mains[0]):
        return VlcWindow(pid, None, None)
    wins = [(h, _rect(h)) for h in _windows(lambda h: _pid(h) == pid and not user32.IsIconic(h))]
    best = None
    for h, r in wins:
        area = (r[2] - r[0]) * (r[3] - r[1])
        if best is None or area > best[0]:
            best = (area, r, h)
    if not best:
        return VlcWindow(pid, None, None)
    rect, full = _visible_part(best[2], best[1])
    return VlcWindow(pid, rect, _bar_top(rect, [r for h, r in wins if h != best[2]]) if full else None)


def _bar_top(rect, others):
    """Tam ekranda VLC'nin alttaki kontrol çubuğu ayrı, küçük bir pencere olarak çıkar."""
    l, t, r, b = rect
    tops = [o[1] for o in others
            if o[0] >= l and o[2] <= r and o[3] <= b + 2
            and o[1] > t + (b - t) * 2 // 3 and o[3] - o[1] < (b - t) // 4]
    return min(tops) if tops else None


def _visible_part(hwnd, r):
    """Pencerenin ekranda görünen kısmı (taşan pencerede altyazı ekran dışına düşmesin)
    ve tam ekran olup olmadığı."""
    mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    if not user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST), ctypes.byref(mi)):
        return r, False
    m, w = mi.rcMonitor, mi.rcWork
    full = r[0] <= m.left and r[1] <= m.top and r[2] >= m.right and r[3] >= m.bottom
    area = m if full else w  # tam ekran / görev çubuğu hariç
    clipped = (max(r[0], area.left), max(r[1], area.top), min(r[2], area.right), min(r[3], area.bottom))
    if clipped[2] - clipped[0] < 100 or clipped[3] - clipped[1] < 100:
        return r, full
    return clipped, full


def foreground_pid():
    h = user32.GetForegroundWindow()
    return _pid(h) if h else 0


def _hwnd(tk_win):
    return user32.GetParent(tk_win.winfo_id())


def make_passive(tk_win, color_key=None):
    """Tıklanınca odak çalmayan, görev çubuğunda görünmeyen pencere.

    color_key verilirse (#rrggbb) o renk şeffaf yapılır.
    """
    h = _hwnd(tk_win)
    style = user32.GetWindowLongW(h, GWL_EXSTYLE)
    if color_key:
        style |= WS_EX_LAYERED
    user32.SetWindowLongW(h, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    if color_key:
        set_layered(tk_win, color_key, 255)
    user32.SetWindowPos(h, None, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOZORDER | SWP_FRAMECHANGED)


def set_layered(tk_win, color_key, alpha):
    """color_key rengini şeffaf, geri kalanı alpha (0-255) opaklıkta göster."""
    r, g, b = int(color_key[1:3], 16), int(color_key[3:5], 16), int(color_key[5:7], 16)
    user32.SetLayeredWindowAttributes(_hwnd(tk_win), r | (g << 8) | (b << 16),
                                      max(0, min(255, int(alpha))), LWA_COLORKEY | LWA_ALPHA)


def dark_titlebar(tk_win):
    """Windows 10/11'de pencerenin başlık çubuğunu koyu yapar."""
    try:
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(_hwnd(tk_win)), 20,
                                                   ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def keep_on_top(tk_win):
    user32.SetWindowPos(_hwnd(tk_win), HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
