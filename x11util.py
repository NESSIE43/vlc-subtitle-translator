"""Linux'a (X11) özel yardımcılar: VLC penceresini bulma, pencereyi şekillendirme.

Ek paket gerekmez; libX11 ve libXext ctypes ile kullanılır. Wayland oturumunda
VLC 3 ve Tk XWayland üzerinden çalıştığı için çoğunlukla yine çalışır.
"""
import ctypes
import ctypes.util
import os
from collections import namedtuple

OWN_PID = os.getpid()
COLOR_KEY = False  # X11'de pencere içinde şeffaf renk yok; pencere şekillendirilir

VlcWindow = namedtuple('VlcWindow', 'pid rect bar_top')  # rect None => simge durumunda

Window = ctypes.c_ulong
Atom = ctypes.c_ulong


class XWindowAttributes(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int), ('y', ctypes.c_int), ('width', ctypes.c_int),
                ('height', ctypes.c_int), ('border_width', ctypes.c_int), ('depth', ctypes.c_int),
                ('visual', ctypes.c_void_p), ('root', Window), ('class_', ctypes.c_int),
                ('bit_gravity', ctypes.c_int), ('win_gravity', ctypes.c_int),
                ('backing_store', ctypes.c_int), ('backing_planes', ctypes.c_ulong),
                ('backing_pixel', ctypes.c_ulong), ('save_under', ctypes.c_int),
                ('colormap', ctypes.c_ulong), ('map_installed', ctypes.c_int),
                ('map_state', ctypes.c_int), ('all_event_masks', ctypes.c_long),
                ('your_event_mask', ctypes.c_long), ('do_not_propagate_mask', ctypes.c_long),
                ('override_redirect', ctypes.c_int), ('screen', ctypes.c_void_p)]


class XRectangle(ctypes.Structure):
    _fields_ = [('x', ctypes.c_short), ('y', ctypes.c_short),
                ('width', ctypes.c_ushort), ('height', ctypes.c_ushort)]


IS_VIEWABLE = 2
_x = None


class _X:
    def __init__(self):
        x = self.lib = ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XDefaultRootWindow.restype = Window
        x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x.XInternAtom.restype = Atom
        x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, Window, Atom, ctypes.c_long, ctypes.c_long, ctypes.c_int, Atom,
            ctypes.POINTER(Atom), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p)]
        x.XFree.argtypes = [ctypes.c_void_p]
        x.XGetWindowAttributes.argtypes = [ctypes.c_void_p, Window, ctypes.POINTER(XWindowAttributes)]
        x.XTranslateCoordinates.argtypes = [
            ctypes.c_void_p, Window, Window, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(Window)]
        x.XQueryTree.argtypes = [ctypes.c_void_p, Window, ctypes.POINTER(Window), ctypes.POINTER(Window),
                                 ctypes.POINTER(ctypes.POINTER(Window)), ctypes.POINTER(ctypes.c_uint)]
        x.XFlush.argtypes = [ctypes.c_void_p]
        x.XSetErrorHandler.restype = ctypes.c_void_p
        x.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        self.dpy = x.XOpenDisplay(None)
        if not self.dpy:
            raise OSError('X ekranına bağlanılamadı')
        # Pencere bu arada kapanırsa X hatası programı kapatmasın.
        self._on_error = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda d, e: 0)
        x.XSetErrorHandler(ctypes.cast(self._on_error, ctypes.c_void_p))
        self.root = x.XDefaultRootWindow(self.dpy)
        self.atoms = {}
        try:
            ext = self.ext = ctypes.CDLL(ctypes.util.find_library('Xext') or 'libXext.so.6')
            ext.XShapeCombineRectangles.argtypes = [
                ctypes.c_void_p, Window, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.POINTER(XRectangle), ctypes.c_int, ctypes.c_int, ctypes.c_int]
        except OSError:
            self.ext = None

    def atom(self, name):
        if name not in self.atoms:
            self.atoms[name] = self.lib.XInternAtom(self.dpy, name.encode(), False)
        return self.atoms[name]

    def prop(self, win, name):
        """Pencere özelliği: 32 bit ise sayı listesi, 8 bit ise bytes, yoksa None."""
        typ, fmt = Atom(), ctypes.c_int()
        n, after, data = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p()
        ok = self.lib.XGetWindowProperty(self.dpy, win, self.atom(name), 0, 1 << 16, False, 0,
                                         ctypes.byref(typ), ctypes.byref(fmt), ctypes.byref(n),
                                         ctypes.byref(after), ctypes.byref(data))
        if ok != 0 or not data.value:
            return None
        try:
            if fmt.value == 32:  # Xlib 32 bitlik özellikleri C long dizisi olarak verir
                return list(ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[:n.value])
            if fmt.value == 8:
                return ctypes.string_at(data, n.value)
            return None
        finally:
            self.lib.XFree(data)

    def title(self, win):
        raw = self.prop(win, '_NET_WM_NAME') or self.prop(win, 'WM_NAME') or b''
        return raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else ''

    def pid(self, win):
        v = self.prop(win, '_NET_WM_PID')
        return v[0] if v else 0

    def attrs(self, win):
        a = XWindowAttributes()
        return a if self.lib.XGetWindowAttributes(self.dpy, win, ctypes.byref(a)) else None

    def rect(self, win):
        """Pencerenin (çerçevesiz) ekran koordinatları."""
        a = self.attrs(win)
        if a is None:
            return None
        x, y, child = ctypes.c_int(), ctypes.c_int(), Window()
        self.lib.XTranslateCoordinates(self.dpy, win, self.root, 0, 0, ctypes.byref(x),
                                       ctypes.byref(y), ctypes.byref(child))
        return x.value, y.value, x.value + a.width, y.value + a.height

    def children(self, win):
        root, parent = Window(), Window()
        kids, n = ctypes.POINTER(Window)(), ctypes.c_uint()
        if not self.lib.XQueryTree(self.dpy, win, ctypes.byref(root), ctypes.byref(parent),
                                   ctypes.byref(kids), ctypes.byref(n)):
            return []
        try:
            return [kids[i] for i in range(n.value)]
        finally:
            if kids:
                self.lib.XFree(kids)


    def clients(self):
        """Pencere yöneticisinin yönettiği pencereler."""
        listed = self.prop(self.root, '_NET_CLIENT_LIST')
        if listed:
            return listed
        # Liste yayımlamayan pencere yöneticileri: WM_STATE özelliği olan pencereleri ara.
        found = []
        for top in self.children(self.root):
            if self.prop(top, 'WM_STATE') is not None:
                found.append(top)
            else:
                found.extend(w for w in self.children(top) if self.prop(w, 'WM_STATE') is not None)
        return found


def _get():
    global _x
    if _x is None:
        try:
            _x = _X()
        except OSError:
            _x = False
    return _x or None


def enable_dpi_awareness():
    pass


def dark_titlebar(tk_win):
    pass


def make_passive(tk_win, color_key=None):
    pass  # overrideredirect pencereler zaten odak almaz ve görev çubuğunda görünmez


def set_layered(tk_win, color_key, alpha):
    pass


def keep_on_top(tk_win):
    tk_win.lift()


def _frame(tk_win):
    return int(tk_win.wm_frame(), 16)


def shape(tk_win, rects):
    """Pencerenin sadece verilen dikdörtgenlerden oluşan kısmını görünür yapar."""
    x = _get()
    if not x or not x.ext:
        return
    arr = (XRectangle * max(1, len(rects)))(*[XRectangle(int(a), int(b), int(c - a), int(d - b))
                                              for a, b, c, d in rects])
    # ShapeBounding = 0, ShapeSet = 0, Unsorted = 0
    x.ext.XShapeCombineRectangles(x.dpy, _frame(tk_win), 0, 0, 0, arr, len(rects), 0, 0)
    x.lib.XFlush(x.dpy)


def foreground_pid():
    x = _get()
    if not x:
        return 0
    active = x.prop(x.root, '_NET_ACTIVE_WINDOW')
    return x.pid(active[0]) if active and active[0] else 0


def _bar_top(rect, others):
    """Tam ekranda VLC'nin alttaki kontrol çubuğu ayrı, küçük bir pencere olarak çıkar."""
    l, t, r, b = rect
    tops = [o[1] for o in others
            if o[0] >= l and o[2] <= r and o[3] <= b + 2
            and o[1] > t + (b - t) * 2 // 3 and o[3] - o[1] < (b - t) // 4]
    return min(tops) if tops else None


def find_vlc():
    """Takip edilecek VLC penceresi. Tam ekranda video penceresi en büyüğü olur."""
    x = _get()
    if not x:
        return None
    clients = x.clients()
    mains = [w for w in clients if x.title(w).endswith('VLC media player')]
    if not mains:
        return None
    pid = x.pid(mains[0])
    hidden, full_atom = x.atom('_NET_WM_STATE_HIDDEN'), x.atom('_NET_WM_STATE_FULLSCREEN')
    if hidden in (x.prop(mains[0], '_NET_WM_STATE') or []):
        return VlcWindow(pid, None, None)
    best = None
    # PID bilinmiyorsa (pencere bildirmemişse) sadece başlığı eşleşen pencereler.
    for w in clients if pid else mains:
        if pid and x.pid(w) != pid:
            continue
        state = x.prop(w, '_NET_WM_STATE') or []
        a = x.attrs(w)
        if hidden in state or a is None or a.map_state != IS_VIEWABLE:
            continue
        r = x.rect(w)
        area = (r[2] - r[0]) * (r[3] - r[1])
        if best is None or area > best[0]:
            best = (area, r, full_atom in state)
    if not best:
        return VlcWindow(pid, None, None)
    _, rect, full = best
    screen = x.rect(x.root)
    if screen and rect[0] <= screen[0] and rect[1] <= screen[1] and rect[2] >= screen[2] and rect[3] >= screen[3]:
        full = True  # tam ekran durumunu bildirmeyen pencere yöneticileri
    bar = None
    if full:
        # Tam ekran kontrol çubuğu pencere yöneticisinin yönetmediği (override-redirect) bir penceredir.
        others = []
        for w in x.children(x.root):
            a = x.attrs(w)
            if a and a.map_state == IS_VIEWABLE and a.override_redirect and pid and x.pid(w) == pid:
                others.append(x.rect(w))
        bar = _bar_top(rect, others)
    return VlcWindow(pid, rect, bar)
