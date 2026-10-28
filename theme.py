"""Koyu arayüz teması ve ortak renkler."""
import sys
import tkinter as tk
from tkinter import ttk

import osutil
from i18n import _

FONT = 'Segoe UI' if sys.platform == 'win32' else 'DejaVu Sans'
BG = '#131418'
CARD = '#1c1d23'
CARD2 = '#25272f'
BORDER = '#30323c'
FG = '#e8e9ee'
MUTED = '#8b90a0'
ACCENT = '#7c83fd'
ACCENT_HI = '#959bff'
OK = '#4ade80'
ERR = '#f87171'

COLORS = {'green': '#4ade80', 'yellow': '#facc15', 'red': '#f87171'}
LABELS = {'green': _('Biliyorum'), 'yellow': _('Öğreniyorum'), 'red': _('Bilmiyorum')}
FAV = '#fbbf24'


def _rgbt(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def _paint(w, h, layers, under):
    """Kenarları yumuşatılmış küçük resim çizer.

    layers(fx, fy) piksel içindeki bir noktanın rengini (#rrggbb) ya da boş
    olduğunu (None) döner. Tamamen boş pikseller şeffaf, yarı dolu pikseller
    `under` rengiyle karıştırılır.
    """
    img = tk.PhotoImage(width=w, height=h)
    under = _rgbt(under)
    n = 4
    clear = []
    for y in range(h):
        row = []
        for x in range(w):
            acc, hits = [0, 0, 0], 0
            for sy in range(n):
                for sx in range(n):
                    c = layers(x + (sx + 0.5) / n, y + (sy + 0.5) / n)
                    if c is not None:
                        hits += 1
                        for i, v in enumerate(_rgbt(c)):
                            acc[i] += v
            if hits == 0:
                row.append('#000000')
                clear.append((x, y))
                continue
            k = hits / (n * n)
            rgb = [acc[i] / hits * k + under[i] * (1 - k) for i in range(3)]
            row.append('#%02x%02x%02x' % tuple(int(v) for v in rgb))
        img.put('{' + ' '.join(row) + '}', to=(0, y))
    for x, y in clear:
        img.transparency_set(x, y, True)
    return img


def _in_round_rect(x, y, x0, y0, x1, y1, r):
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _near_segment(px, py, ax, ay, bx, by, t):
    dx, dy = bx - ax, by - ay
    k = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return (px - ax - k * dx) ** 2 + (py - ay - k * dy) ** 2 <= t * t


def _images(root, ui):
    """Onay kutusu ve kaydırıcı için resimler (referansları kaybolmasın diye root'ta tutulur)."""
    sz = round(18 * ui)
    gap = round(9 * ui)
    r = 4 * ui

    def box(on):
        def layer(x, y):
            if not _in_round_rect(x, y, 0, 0, sz, sz, r):
                return None
            if on:
                t = 1.2 * ui
                if (_near_segment(x, y, sz * .26, sz * .52, sz * .43, sz * .70, t)
                        or _near_segment(x, y, sz * .43, sz * .70, sz * .76, sz * .32, t)):
                    return '#ffffff'
                return ACCENT
            inner = _in_round_rect(x, y, 1.5 * ui, 1.5 * ui, sz - 1.5 * ui, sz - 1.5 * ui, r - 1.5 * ui)
            return CARD2 if inner else '#4a4d5a'
        return _paint(sz + gap, sz, layer, CARD)

    def dot(on):
        def layer(x, y):
            dist = (x - sz / 2) ** 2 + (y - sz / 2) ** 2
            if dist > (sz / 2) ** 2:
                return None
            if dist > (sz / 2 - 1.5 * ui) ** 2:
                return ACCENT if on else '#4a4d5a'
            return '#ffffff' if on and dist <= (sz / 2 - 5 * ui) ** 2 else (ACCENT if on else CARD2)
        return _paint(sz + gap, sz, layer, CARD)

    d = round(18 * ui)

    def knob(color):
        def layer(x, y):
            dist = (x - d / 2) ** 2 + (y - d / 2) ** 2
            if dist > (d / 2) ** 2:
                return None
            return '#ffffff' if dist <= (d / 2 - 3 * ui) ** 2 else color
        return _paint(d, d, layer, CARD)

    th = max(2, round(4 * ui))
    tw = round(24 * ui)

    def trough(x, y):
        top = (d - th) / 2
        return CARD2 if _in_round_rect(x, y, 0, top, tw, top + th, th / 2) else None

    imgs = {'off': box(False), 'on': box(True), 'roff': dot(False), 'ron': dot(True), 'knob': knob(ACCENT), 'knob_hi': knob(ACCENT_HI),
            'trough': _paint(tw, d, trough, CARD)}
    root._theme_images = imgs
    return imgs


def apply(root):
    root.configure(bg=BG)
    s = ttk.Style(root)
    s.theme_use('clam')
    ui = root.winfo_fpixels('1i') / 96
    imgs = _images(root, ui)
    s.element_create('Fancy.Checkbutton.indicator', 'image', imgs['off'], ('selected', imgs['on']),
                     sticky='w')
    s.layout('TCheckbutton', [('Checkbutton.padding', {'sticky': 'nswe', 'children': [
        ('Fancy.Checkbutton.indicator', {'side': 'left', 'sticky': ''}),
        ('Checkbutton.label', {'side': 'left', 'sticky': 'nswe'})]})])
    s.element_create('Fancy.Radiobutton.indicator', 'image', imgs['roff'], ('selected', imgs['ron']),
                     sticky='w')
    s.layout('TRadiobutton', [('Radiobutton.padding', {'sticky': 'nswe', 'children': [
        ('Fancy.Radiobutton.indicator', {'side': 'left', 'sticky': ''}),
        ('Radiobutton.label', {'side': 'left', 'sticky': 'nswe'})]})])
    s.element_create('Fancy.Scale.trough', 'image', imgs['trough'], border=(round(8 * ui), 0), sticky='ew')
    s.element_create('Fancy.Scale.slider', 'image', imgs['knob'], ('active', imgs['knob_hi']),
                     ('pressed', imgs['knob_hi']))
    s.layout('Horizontal.TScale', [('Fancy.Scale.trough', {'sticky': 'nswe', 'children': [
        ('Fancy.Scale.slider', {'side': 'left', 'sticky': ''})]})])
    s.configure('.', background=BG, foreground=FG, fieldbackground=CARD2, bordercolor=BORDER,
                lightcolor=BORDER, darkcolor=BORDER, troughcolor=CARD2, focuscolor=ACCENT,
                selectbackground=ACCENT, selectforeground='#ffffff', font=(FONT, 10))
    s.configure('TFrame', background=BG)
    s.configure('Card.TFrame', background=CARD)
    s.configure('TLabel', background=BG, foreground=FG)
    s.configure('Card.TLabel', background=CARD, foreground=FG)
    s.configure('Muted.TLabel', background=BG, foreground=MUTED)
    s.configure('CardMuted.TLabel', background=CARD, foreground=MUTED, font=(FONT, 9))
    s.configure('CardTitle.TLabel', background=CARD, foreground=FG, font=(FONT, 11, 'bold'))
    s.configure('Title.TLabel', background=BG, foreground=FG, font=(FONT, 17, 'bold'))

    s.configure('TButton', background=CARD2, foreground=FG, padding=(14, 7), borderwidth=0,
                relief='flat', focusthickness=0)
    s.map('TButton', background=[('pressed', BORDER), ('active', '#30323d')])
    s.configure('Accent.TButton', background=ACCENT, foreground='#ffffff', font=(FONT, 10, 'bold'))
    s.map('Accent.TButton', background=[('pressed', '#6b72ee'), ('active', ACCENT_HI)])

    s.configure('TCheckbutton', background=CARD, foreground=FG, padding=(0, 3))
    s.map('TCheckbutton', background=[('active', CARD)], foreground=[('active', '#ffffff')])
    s.configure('TRadiobutton', background=CARD, foreground=FG, padding=(0, 3))
    s.map('TRadiobutton', background=[('active', CARD)], foreground=[('active', '#ffffff')])
    s.configure('Horizontal.TScale', background=CARD)

    s.configure('TEntry', fieldbackground=CARD2, foreground=FG, insertcolor=FG, padding=6)
    s.map('TEntry', fieldbackground=[('disabled', CARD)], foreground=[('disabled', MUTED)])
    s.configure('TCombobox', fieldbackground=CARD2, background=CARD2, foreground=FG,
                arrowcolor=FG, padding=5)
    s.map('TCombobox', fieldbackground=[('readonly', CARD2)], foreground=[('readonly', FG)],
          selectbackground=[('readonly', CARD2)], selectforeground=[('readonly', FG)])
    root.option_add('*TCombobox*Listbox.background', CARD2)
    root.option_add('*TCombobox*Listbox.foreground', FG)
    root.option_add('*TCombobox*Listbox.selectBackground', ACCENT)
    root.option_add('*TCombobox*Listbox.font', (FONT, 10))

    s.configure('TSpinbox', fieldbackground=CARD2, foreground=FG, arrowcolor=FG)

    s.configure('TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    s.configure('TNotebook.Tab', background=BG, foreground=MUTED, padding=(18, 9),
                borderwidth=0, font=(FONT, 10, 'bold'))
    s.map('TNotebook.Tab', background=[('selected', CARD), ('active', CARD2)],
          foreground=[('selected', FG)], lightcolor=[('selected', CARD)])

    s.configure('Treeview', background=CARD, fieldbackground=CARD, foreground=FG, rowheight=28,
                borderwidth=0)
    s.configure('Treeview.Heading', background=CARD2, foreground=MUTED, relief='flat',
                font=(FONT, 9, 'bold'), padding=6)
    s.map('Treeview', background=[('selected', '#34376a')], foreground=[('selected', '#ffffff')])
    s.map('Treeview.Heading', background=[('active', BORDER)])
    s.configure('Vertical.TScrollbar', background=CARD2, troughcolor=CARD, arrowcolor=MUTED,
                borderwidth=0)


def window(win):
    """Yeni bir pencereyi temaya uydurur (koyu başlık çubuğu dahil)."""
    win.configure(bg=BG)
    win.update_idletasks()
    osutil.dark_titlebar(win)


def card(parent, title=None, subtitle=None):
    """Başlıklı, koyu kart. İçerik eklenecek çerçeveyi döner."""
    outer = ttk.Frame(parent, style='Card.TFrame', padding=16)
    if title:
        ttk.Label(outer, text=title, style='CardTitle.TLabel').pack(anchor='w')
    if subtitle:
        ttk.Label(outer, text=subtitle, style='CardMuted.TLabel', wraplength=440,
                  justify='left').pack(anchor='w', pady=(2, 0))
    inner = ttk.Frame(outer, style='Card.TFrame')
    inner.pack(fill='both', expand=True, pady=(10 if title else 0, 0))
    return outer, inner


def swatch(parent, color, command):
    """Tıklanınca renk seçtiren küçük renk kutusu."""
    sw = tk.Label(parent, bg=color, width=4, height=1, cursor='hand2', relief='flat',
                  highlightthickness=1, highlightbackground=BORDER)
    sw.bind('<Button-1>', lambda e: command())
    return sw
