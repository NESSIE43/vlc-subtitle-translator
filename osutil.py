"""İşletim sistemine özel pencere işlemleri: Windows'ta winutil, Linux'ta x11util."""
import sys

if sys.platform == 'win32':
    from winutil import (OWN_PID, VlcWindow, dark_titlebar, enable_dpi_awareness,  # noqa: F401
                         find_vlc, foreground_pid, keep_on_top, make_passive, set_layered)
    COLOR_KEY = True  # pencerede bir renk tamamen şeffaf yapılabiliyor

    def shape(tk_win, rects):
        pass
else:
    from x11util import (COLOR_KEY, OWN_PID, VlcWindow, dark_titlebar,  # noqa: F401
                         enable_dpi_awareness, find_vlc, foreground_pid, keep_on_top,
                         make_passive, set_layered, shape)
