"""VLC penceresinin üstünde gösterilen altyazı ve kelime çeviri penceresi.

Windows'ta altyazı iki şeffaf pencereden oluşur: alttaki arka plan kutularını
ayarlanabilir opaklıkta, üstteki yazıyı tam opak çizer. Linux'ta (X11) pencere içinde
şeffaf renk olmadığından tek pencere satır kutularının şekline kırpılır. Fare takibi
pencere olaylarıyla değil koordinatla yapılır; böylece şeffaf kısımlarda da kelime algılanır.
"""
import math
import time
import tkinter as tk
import tkinter.font as tkfont

import osutil
from i18n import _
from storage import normalize
from theme import COLORS, FAV, FONT, LABELS
from translator import TranslateError, translate_sentence, translate_word

KEY_BG = '#ff00fe'   # arka plan penceresinde şeffaf sayılan renk
KEY_TXT = '#010101'  # yazı penceresinde şeffaf sayılan renk (kenar yumuşatması koyu kalsın)
OUTLINE = '#000000'
HOVER = '#3d4050'
OFF = '1x1+-20000+-20000'

PBG = '#1c1d23'
PBG2 = '#2a2c35'
PBORDER = '#3a3d48'


def make_fonts(settings, scale=1.0):
    size = max(6, int(round(settings['font_size'] * scale)))
    weight = 'bold' if settings['bold'] else 'normal'
    fam = settings['font_family']
    return (tkfont.Font(family=fam, size=size, weight=weight),
            tkfont.Font(family=fam, size=size, weight=weight, underline=True))


class SubtitleLayout:
    """Metni satırlara böler; kutu ve kelime konumlarını hesaplar."""

    def __init__(self, text, font, maxw, rounded, outline):
        lh = font.metrics('linespace')
        space = font.measure(' ')
        pad_x, pad_y, gap = round(lh * 0.38), round(lh * 0.06), round(lh * 0.12)
        self.outline = max(1, round(lh / 24)) if outline else 0
        self.radius = round(lh * 0.28) if rounded else 0
        m = self.outline + 1

        rows = []
        for line in text.split('\n'):
            cur, width = [], 0
            for tok in line.split():
                tw = font.measure(tok)
                add = tw + (space if cur else 0)
                if cur and width + add > maxw - 2 * pad_x:
                    rows.append((cur, width, line))
                    cur, width, add = [], 0, tw
                cur.append((tok, tw))
                width += add
            if cur:
                rows.append((cur, width, line))

        self.boxes, self.words = [], []
        if not rows:
            self.width = self.height = 0
            return
        inner_w = max(w for _, w, _ in rows) + 2 * pad_x
        row_h = lh + 2 * pad_y
        self.width = inner_w + 2 * m
        self.height = len(rows) * row_h + (len(rows) - 1) * gap + 2 * m
        for i, (toks, w, line) in enumerate(rows):
            x0 = m + (inner_w - w - 2 * pad_x) // 2
            y0 = m + i * (row_h + gap)
            self.boxes.append((x0, y0, x0 + w + 2 * pad_x, y0 + row_h))
            x = x0 + pad_x
            for tok, tw in toks:
                self.words.append((tok, x, y0 + pad_y, tw, lh, line))
                x += tw + space


def rounded_rect(canvas, x0, y0, x1, y1, r, **kw):
    if r <= 0:
        return canvas.create_rectangle(x0, y0, x1, y1, width=0, **kw)
    r = min(r, (x1 - x0) // 2, (y1 - y0) // 2)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return canvas.create_polygon(pts, smooth=True, width=0, **kw)


def corner_inset(r, d, h):
    """Yuvarlak köşeli kutuda, üstten d. satırın yandan ne kadar içeride başladığı."""
    if r <= 0:
        return 0
    k = min(d, h - 1 - d)
    if k >= r:
        return 0
    dy = r - k - 0.5
    return r - math.sqrt(max(0.0, r * r - dy * dy))


def shape_rects(layout):
    """Yuvarlak köşeli kutuları dikdörtgenlerle kaplar (X11'de pencere şekli için)."""
    rects = []
    for x0, y0, x1, y1 in layout.boxes:
        h, r = y1 - y0, layout.radius
        k = min(r, h // 2)
        for d in range(k):
            inset = round(corner_inset(r, d, h))
            rects.append((x0 + inset, y0 + d, x1 - inset, y0 + d + 1))
            rects.append((x0 + inset, y1 - 1 - d, x1 - inset, y1 - d))
        rects.append((x0, y0 + k, x1, y1 - k))
    return rects


def draw_words(canvas, layout, font, font_fav, style_of, text_color, ox=0, oy=0):
    """Kelimeleri (varsa kenarlıklı) çizer. Etkileşimli kelimelerin listesini döner."""
    o = layout.outline
    offsets = [(dx, dy) for dx in (-o, 0, o) for dy in (-o, 0, o) if dx or dy] if o else []
    words = []
    for tok, x, y, tw, lh, line in layout.words:
        key = normalize(tok)
        color, fav = style_of(key) if key else (None, False)
        f = font_fav if fav else font
        for dx, dy in offsets:
            canvas.create_text(ox + x + dx, oy + y + dy, text=tok, font=f, fill=OUTLINE, anchor='nw',
                               tags=('outline',))
        item = canvas.create_text(ox + x, oy + y, text=tok, font=f, anchor='nw',
                                  fill=COLORS.get(color, text_color))
        if key:
            words.append({'key': key, 'line': line, 'item': item,
                          'rect': (ox + x, oy + y, ox + x + tw, oy + y + lh)})
    return words


class Overlay:
    def __init__(self, app):
        self.app = app
        self.bgwin, self.bg_canvas = self._make_window(KEY_BG)
        self.win, self.canvas = self._make_window(KEY_TXT)
        self.font = self.font_fav = None
        self.text = ''
        self.words = []
        self.rect = None
        self.bar_top = None
        self.pointer_at_build = None
        self._geo = None
        self._shape = []
        self._ticks = 0
        self._pending = None
        self._pending_since = 0.0
        self.popup = WordPopup(app, self)
        self.update_style()

    def _make_window(self, key):
        w = tk.Toplevel(self.app.root)
        w.overrideredirect(True)
        w.configure(bg=key)
        w.attributes('-topmost', True)
        if osutil.COLOR_KEY:
            w.attributes('-transparentcolor', key)
        w.geometry(OFF)
        c = tk.Canvas(w, bg=key, highlightthickness=0, bd=0, width=1, height=1)
        c.pack(fill='both', expand=True)
        w.update_idletasks()
        osutil.make_passive(w, key)
        return w, c

    # -- görünüm -------------------------------------------------------
    def update_style(self):
        self.font, self.font_fav = make_fonts(self.app.settings)
        osutil.set_layered(self.bgwin, KEY_BG, 255 * self.app.settings['bg_opacity'] / 100)
        self.rebuild()

    def _style_of(self, key):
        store = self.app.store
        return store.color(key), store.is_fav(key)

    def refresh_styles(self):
        """Kelime renk/favori değişince yeniden çiz; açık çeviri penceresi kapanmasın."""
        if not self.words:
            return
        anchor_key = self.popup.key if self.popup.active else None
        anchor_rect = self.popup.anchor['rect'] if self.popup.active else None
        self._draw()
        if anchor_key:
            for w in self.words:
                if w['key'] == anchor_key and w['rect'] == anchor_rect:
                    self.popup.anchor = w
                    self.highlight(w)
                    return
            self.popup.hide()

    # -- içerik --------------------------------------------------------
    def set_text(self, text):
        if text == self.text:
            return
        if self.popup.active:
            if self.app.hover_paused or self.app.vlc_state != 'playing':
                return  # video duraklatılmışken satır sabit kalsın
            self.popup.hide()  # video akıyorsa eski satırda takılı kalma
        self.text = text
        self.rebuild()

    def rebuild(self):
        self.popup.hide()
        self._draw()
        # fare hiç kıpırdamadan altına gelen kelime çeviri açmasın
        self.pointer_at_build = self.win.winfo_pointerxy()
        self._pending = None

    def _draw(self):
        s = self.app.settings
        self.canvas.delete('all')
        self.bg_canvas.delete('all')
        self.words = []
        layout = None
        if self.text and self.rect:
            maxw = (self.rect[2] - self.rect[0]) * s['max_width_pct'] / 100
            layout = SubtitleLayout(self.text, self.font, maxw, s['rounded'], s['outline'])
            if osutil.COLOR_KEY:
                for box in layout.boxes:
                    rounded_rect(self.bg_canvas, *box, layout.radius, fill=s['bg_color'])
            else:
                self.canvas.configure(bg=s['bg_color'])
                self._shape = shape_rects(layout)
            self.words = draw_words(self.canvas, layout, self.font, self.font_fav,
                                    self._style_of, s['text_color'])
        self.place(layout)

    def highlight(self, word):
        self.canvas.delete('hl')
        if word is not None:
            x0, y0, x1, y1 = word['rect']
            self.canvas.create_rectangle(x0 - 4, y0, x1 + 4, y1, fill=HOVER, width=0, tags=('hl',))
            self.canvas.tag_lower('hl')

    # -- konum ---------------------------------------------------------
    def place(self, layout=None):
        if layout is None and self.words:
            layout_w, layout_h = int(self.canvas['width']), int(self.canvas['height'])
        elif layout is not None and layout.width:
            layout_w, layout_h = layout.width, layout.height
        else:
            layout_w = layout_h = 0
        if not layout_w or not self.rect:
            geo = OFF
        else:
            for c in (self.canvas, self.bg_canvas):
                c.configure(width=layout_w, height=layout_h)
            l, t, r, b = self.rect
            x = l + (r - l - layout_w) // 2
            y = int(b - (b - t) * self.app.settings['bottom_pct'] / 100 - layout_h)
            if self.bar_top is not None:
                y = min(y, self.bar_top - 6 - layout_h)
            geo = '%dx%d+%d+%d' % (layout_w, layout_h, x, y)
        if geo != self._geo:
            self._geo = geo
            if osutil.COLOR_KEY:
                self.bgwin.geometry(geo)
            self.win.geometry(geo)
            # Tk konumu boşta uygular; ondan önce SetWindowPos çağrılırsa Tk eski
            # konumu yeni sanıp taşımayı iptal eder. Önce uygula, sonra öne al.
            self.win.update_idletasks()
            self._raise()
        if not osutil.COLOR_KEY and geo != OFF and layout is not None:
            osutil.shape(self.win, self._shape)

    def _raise(self):
        if osutil.COLOR_KEY:
            osutil.keep_on_top(self.bgwin)
        osutil.keep_on_top(self.win)  # yazı, arka planın üstünde kalsın
        if self.popup.active:
            osutil.keep_on_top(self.popup.win)

    def follow(self, info):
        """VLC penceresinin konumunu takip et (her 250 ms)."""
        rect = None
        if info and info.rect and osutil.foreground_pid() in (info.pid, osutil.OWN_PID):
            rect = info.rect
        if rect is None:
            self.popup.hide()
        old, self.rect = self.rect, rect
        # Tam ekran kontrol çubuğu bir kez görülünce altyazı onun üstünde kalsın;
        # çubuk gizlenince aşağı inip fareden kaçmasın.
        bar = info.bar_top if rect and info else None
        old_bar = self.bar_top
        if old != rect:
            self.bar_top = bar
        elif bar is not None and (old_bar is None or bar < old_bar):
            self.bar_top = bar
        if old != rect:
            if old and rect and (old[2] - old[0], old[3] - old[1]) == (rect[2] - rect[0], rect[3] - rect[1]):
                self.place()  # sadece taşındı
            else:
                self.rebuild()  # boyut değişti, satırları yeniden kır
        elif self.bar_top != old_bar:
            self.place()
            if self.popup.active:
                self.popup._position()
        self._ticks += 1
        if rect and self._ticks % 4 == 0:
            self._raise()

    # -- fare ----------------------------------------------------------
    def word_at(self, px, py, pad=2):
        cx, cy = px - self.canvas.winfo_rootx(), py - self.canvas.winfo_rooty()
        for w in self.words:
            x0, y0, x1, y1 = w['rect']
            if x0 - pad <= cx <= x1 + pad and y0 <= cy <= y1:
                return w
        return None

    def screen_rect(self, word):
        ox, oy = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
        x0, y0, x1, y1 = word['rect']
        return ox + x0, oy + y0, ox + x1, oy + y1

    def poll_pointer(self):
        """Her 40 ms: fare bir kelimenin üstünde biraz durursa çeviriyi aç."""
        if not self.words or not self.rect:
            self._pending = None
            return
        p = self.win.winfo_pointerxy()
        if p == self.pointer_at_build:
            return
        hit = self.word_at(*p)
        if self.popup.active:
            # fare çeviri penceresine giderken arkada kalan (üst satırdaki) kelimeye geçme
            if hit is not None and hit is not self.popup.anchor and not self.popup.contains(*p, 4):
                self.popup.show(hit)
            return
        if hit is None:
            self._pending = None
            return
        now = time.monotonic()
        if hit is not self._pending:
            self._pending, self._pending_since = hit, now
        elif now - self._pending_since >= 0.25:
            self._pending = None
            self.popup.show(hit)


class WordPopup:
    """Kelimenin üstünde çıkan çeviri + renk + favori penceresi."""

    def __init__(self, app, overlay):
        self.app, self.overlay = app, overlay
        win = self.win = tk.Toplevel(app.root)
        win.overrideredirect(True)
        win.configure(bg=PBORDER)
        win.attributes('-topmost', True)
        win.geometry(OFF)
        self.inner = None
        self.active = False
        self.anchor = None
        self.key = None
        self.line = ''
        self.info = None
        self.sentence = None
        self._misses = 0
        win.update_idletasks()
        osutil.make_passive(win)

    def show(self, word):
        first = not self.active
        if first or word['key'] != self.key:
            self.sentence = None
        self.anchor, self.key, self.line, self.active = word, word['key'], word['line'], True
        self.overlay.highlight(word)
        key, pair, opts = self.key, self.app.lang_pair(), self.app.translate_opts()
        self.info = self.app.tcache.get(pair, key)
        if self.info is None:
            self.app.run_bg(lambda: translate_word(key, *opts),
                            lambda res, err: self._got(pair, key, res, err))
        self.render()
        if first:
            self._misses = 0
            self.win.after(120, self._watch)
            self.app.pause_for_hover()

    @staticmethod
    def _error_text(err):
        return str(err) if isinstance(err, TranslateError) else _('internet bağlantısı?')

    def _got(self, pair, key, res, err):
        if pair != self.app.lang_pair():
            return  # bu arada dil değişti
        if err is None:
            self.app.tcache.put(pair, key, res)
            entry = self.app.store.get(key)
            if entry is not None and not entry.get('tr'):
                self.app.store.set_translation(key, res['main'])
        if self.active and self.key == key:
            self.info = res if err is None else {'error': self._error_text(err)}
            self.render()

    @staticmethod
    def _inside(rect, px, py, pad):
        x0, y0, x1, y1 = rect
        return x0 - pad <= px <= x1 + pad and y0 - pad <= py <= y1 + pad

    def contains(self, px, py, pad=0):
        w = self.win
        rect = (w.winfo_rootx(), w.winfo_rooty(), w.winfo_rootx() + w.winfo_width(),
                w.winfo_rooty() + w.winfo_height())
        return self._inside(rect, px, py, pad)

    def _watch(self):
        if not self.active:
            return
        if self.anchor not in self.overlay.words:
            self.hide()
            return
        px, py = self.win.winfo_pointerxy()
        if self.contains(px, py, 4) or self._inside(self.overlay.screen_rect(self.anchor), px, py, 6):
            self._misses = 0
        else:
            self._misses += 1
            if self._misses >= 2:
                self.hide()
                return
        self.win.after(120, self._watch)

    def hide(self):
        if not self.active:
            return
        self.active = False
        self.overlay.highlight(None)
        self.anchor = None
        self.win.geometry(OFF)
        self.app.resume_after_hover()

    # -- içerik --------------------------------------------------------
    def _chip(self, parent, text, fg, bg, command):
        lbl = tk.Label(parent, text=text, fg=fg, bg=bg, font=(FONT, 9, 'bold'),
                       padx=9, pady=4, cursor='hand2')
        lbl.bind('<Button-1>', lambda e: command())
        return lbl

    def render(self):
        if not self.active:
            return
        store, key = self.app.store, self.key
        entry = store.get(key) or {}
        old = self.inner
        f = self.inner = tk.Frame(self.win, bg=PBG, padx=14, pady=12)

        head = tk.Frame(f, bg=PBG)
        head.pack(fill='x')
        tk.Label(head, text=key, fg='#ffffff', bg=PBG, font=(FONT, 14, 'bold')).pack(side='left')
        fav = bool(entry.get('fav'))
        star = tk.Label(head, text='★' if fav else '☆', fg=FAV if fav else '#8b90a0',
                        bg=PBG, font=(FONT, 17), cursor='hand2')
        star.pack(side='right', padx=(18, 0))
        star.bind('<Button-1>', lambda e: store.toggle_fav(key, self._main(), self._example()))

        info = self.info
        if entry.get('tr'):
            main = entry['tr']
        elif info and not info.get('error'):
            main = info['main']
        else:
            main = None
        if main:
            tk.Label(f, text=main, fg='#f3f4f6', bg=PBG, font=(FONT, 12),
                     wraplength=360, justify='left').pack(anchor='w', pady=(2, 0))
        elif info and info.get('error'):
            tk.Label(f, text=_('Çeviri alınamadı: %s') % info['error'], fg='#f87171', bg=PBG,
                     font=(FONT, 10), wraplength=360, justify='left').pack(anchor='w')
        else:
            tk.Label(f, text=_('çevriliyor…'), fg='#8b90a0', bg=PBG,
                     font=(FONT, 10, 'italic')).pack(anchor='w')
        if info and not info.get('error'):
            for pos, terms in info.get('alts', [])[:3]:
                tk.Label(f, text='%s: %s' % (pos, ', '.join(terms)), fg='#8b90a0', bg=PBG,
                         font=(FONT, 9), wraplength=360, justify='left').pack(anchor='w')

        chips = tk.Frame(f, bg=PBG)
        chips.pack(anchor='w', pady=(10, 0))
        current = entry.get('color')
        for c in ('green', 'yellow', 'red'):
            sel = current == c
            self._chip(chips, ('✓ ' if sel else '') + LABELS[c], '#111111' if sel else COLORS[c],
                       COLORS[c] if sel else PBG2,
                       lambda c=c: store.set_color(key, None if current == c else c,
                                                   self._main(), self._example())
                       ).pack(side='left', padx=(0, 5))
        if current:
            self._chip(chips, '✕', '#d1d5db', PBG2,
                       lambda: store.set_color(key, None)).pack(side='left')

        if self.line:
            if self.sentence is None:
                link = tk.Label(f, text=_('Cümleyi çevir ›'), fg='#959bff', bg=PBG,
                                font=(FONT, 9, 'bold'), cursor='hand2')
                link.pack(anchor='w', pady=(10, 0))
                link.bind('<Button-1>', lambda e: self._translate_line())
            else:
                tk.Label(f, text=self.sentence, fg='#d1d5db', bg=PBG,
                         font=(FONT, 10, 'italic'), wraplength=360,
                         justify='left').pack(anchor='w', pady=(10, 0))

        f.pack(padx=1, pady=1)
        if old is not None:
            old.destroy()
        self._position()

    def _main(self):
        return self.info.get('main') if self.info and not self.info.get('error') else None

    def _example(self):
        return ' '.join(self.line.split())

    def _translate_line(self):
        key, line, opts = self.key, self.line, self.app.translate_opts()
        self.sentence = _('çevriliyor…')
        self.render()

        def done(res, err):
            if self.active and self.key == key and self.line == line:
                self.sentence = res if err is None else _('Çeviri alınamadı: ') + self._error_text(err)
                self.render()
        self.app.run_bg(lambda: translate_sentence(line, *opts), done)

    def _position(self):
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        x0, y0, x1, _ = self.overlay.screen_rect(self.anchor)
        x = (x0 + x1) // 2 - w // 2
        y = y0 - h + 2
        if self.overlay.rect:
            l, t, r, _ = self.overlay.rect
            x = max(l, min(x, r - w))
            y = max(t, y)
        self.win.geometry('%dx%d+%d+%d' % (w, h, x, y))
        self.win.update_idletasks()
        osutil.keep_on_top(self.win)
