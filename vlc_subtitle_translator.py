"""VLC Subtitle Translator (VLC Altyazı Çevirmeni)

VLC'de altyazılı video izlerken altyazıyı VLC penceresinin üstünde kendisi
gösterir; kelimenin üzerine gelince seçtiğin dile çevirisini verir, kelimeleri
renklere ayırmanı ve favorilemeni sağlar.
"""
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
import traceback
import tkinter as tk
import tkinter.font as tkfont
import urllib.error
from tkinter import colorchooser, filedialog, messagebox, ttk

import i18n
import osutil
from storage import DATA_DIR, Settings, TranslationCache, WordStore

osutil.enable_dpi_awareness()
# Arayüz dili, metin sabitleri olan modüller (theme, words_window…) yüklenmeden önce seçilmeli.
i18n.init(Settings()['ui_lang'])

import languages  # noqa: E402
import theme  # noqa: E402
import vlc_setup  # noqa: E402
from i18n import _  # noqa: E402
from overlay import Overlay, SubtitleLayout, corner_inset, draw_words, make_fonts  # noqa: E402
from subtitles import Subtitles, extract_embedded, find_external  # noqa: E402
from theme import CARD, CARD2, COLORS, FAV, FONT, MUTED  # noqa: E402
from translator import TranslateError, translate_sentence  # noqa: E402
from vlc_client import VLCAuthError, VLCClient, uri_to_path  # noqa: E402
from words_window import WordsWindow  # noqa: E402

APP_NAME = _('VLC Altyazı Çevirmeni')
POPULAR_FONTS = ['Segoe UI', 'Arial', 'Calibri', 'Verdana', 'Tahoma', 'Trebuchet MS',
                 'Helvetica', 'Roboto', 'Open Sans', 'Georgia', 'Cambria', 'Consolas']


def log_error(*exc):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, 'hata.log'), 'a', encoding='utf-8') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + ''.join(traceback.format_exception(*exc)))
    traceback.print_exception(*exc)


def _rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def _hex(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(round(v)))) for v in rgb)


class PlaybackClock:
    """VLC'nin tam saniye veren zamanını yerel saatle yumuşatır."""

    def __init__(self):
        self.lock = threading.Lock()
        self.est = 0.0
        self.stamp = time.monotonic()
        self.playing = False
        self.rate = 1.0
        self.delay = 0.0

    def _at(self, now):
        return self.est + ((now - self.stamp) * self.rate if self.playing else 0.0)

    def update(self, st):
        t = float(st.get('time') or 0)
        length = float(st.get('length') or 0)
        pos = float(st.get('position') or 0)
        now = time.monotonic()
        with self.lock:
            cur = self._at(now)
            if abs(cur - t) > 2:  # atlama (ileri/geri sarma)
                cur = pos * length if length else t + 0.5
            self.est = min(max(cur, t), t + 0.999)
            self.stamp = now
            self.playing = st.get('state') == 'playing'
            self.rate = float(st.get('rate') or 1.0)
            self.delay = float(st.get('subtitledelay') or 0.0)

    def stop_now(self):
        with self.lock:
            now = time.monotonic()
            self.est, self.stamp, self.playing = self._at(now), now, False

    def now(self):
        with self.lock:
            return self._at(time.monotonic()) - self.delay


class Preview:
    """Görünüm ayarlarını sahte bir video karesi üstünde canlı gösterir."""

    SAMPLE = 'I have never seen anything\nlike this, my friend.'
    DEMO = {'never': ('red', False), 'seen': ('yellow', False), 'friend': ('green', True)}
    TOP, BOTTOM = (44, 70, 110), (14, 18, 30)

    def __init__(self, parent, app, width, height):
        self.app = app
        self.w, self.h = width, height
        self.canvas = tk.Canvas(parent, width=width, height=height, highlightthickness=0, bd=0, bg=CARD)
        self.fonts = None

    def _grad(self, y):
        t = max(0.0, min(1.0, y / (self.h - 1)))
        return tuple(a + (b - a) * t for a, b in zip(self.TOP, self.BOTTOM))

    def render(self):
        c, s, w, h = self.canvas, self.app.settings, self.w, self.h
        c.delete('all')
        for y in range(0, h, 2):
            c.create_line(0, y + 1, w, y + 1, fill=_hex(self._grad(y)), width=2)
        for i in range(28):  # birkaç yıldız
            x, y = (i * 97) % w, (i * 53) % int(h * 0.35) + 6
            c.create_oval(x, y, x + 2, y + 2, fill='#9fb3d1', width=0)
        c.create_text(12, 10, text=_('ÖNİZLEME'), anchor='nw', fill='#8fa3c4', font=(FONT, 8, 'bold'))

        # Gerçek VLC penceresine göre ölçekle, böylece boyut oranı doğru görünsün.
        rect = self.app.overlay.rect if getattr(self.app, 'overlay', None) else None
        video_w = (rect[2] - rect[0]) if rect else 1600
        self.fonts = make_fonts(s, w / video_w)
        layout = SubtitleLayout(self.SAMPLE, self.fonts[0], w * s['max_width_pct'] / 100,
                                s['rounded'], s['outline'])
        if not layout.width:
            return
        ox = (w - layout.width) // 2
        oy = int(h - h * s['bottom_pct'] / 100 - layout.height)
        alpha = s['bg_opacity'] / 100
        bg = _rgb(s['bg_color'])
        if alpha > 0:
            # yarı saydam kutuyu satır satır, alttaki renkle karıştırarak çiz
            for x0, y0, x1, y1 in layout.boxes:
                bh = y1 - y0
                for d in range(bh):
                    yy = oy + y0 + d
                    inset = corner_inset(layout.radius, d, bh)
                    under = self._grad(yy)
                    col = _hex([b * alpha + u * (1 - alpha) for b, u in zip(bg, under)])
                    c.create_line(ox + x0 + inset, yy, ox + x1 - inset, yy, fill=col)
        draw_words(c, layout, self.fonts[0], self.fonts[1],
                   lambda k: self.DEMO.get(k, (None, False)), s['text_color'], ox, oy)


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.report_callback_exception = log_error
        self.settings = Settings()
        self.store = WordStore()
        self.tcache = TranslationCache()
        self.clock = PlaybackClock()
        self.q = queue.Queue()
        self.subs = None
        self.media_path = None
        self.media_uri = None
        self.load_token = None
        self.conn = None
        self.vlc_state = 'stopped'
        self.hover_paused = False
        self.stopping = False
        self.restart = False
        self.words_window = None
        self._style_job = None

        theme.apply(self.root)
        self.ui = self.root.winfo_fpixels('1i') / 96
        self._build_panel()
        self.overlay = Overlay(self)
        self.preview.render()
        self.store.listeners.append(self._on_store_change)
        self._on_store_change()

        threading.Thread(target=self._poll_loop, daemon=True).start()
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.root.after(40, self._tick)
        self.root.after(250, self._follow)
        self.root.after(400, self._first_run)

    # -- kontrol paneli ------------------------------------------------
    def _build_panel(self):
        root = self.root
        root.title(APP_NAME)
        root.resizable(False, False)
        theme.window(root)

        head = ttk.Frame(root, padding=(20, 16, 20, 10))
        head.pack(fill='x')
        titles = ttk.Frame(head)
        titles.pack(side='left')
        ttk.Label(titles, text=APP_NAME, style='Title.TLabel').pack(anchor='w')
        ttk.Label(titles, text=_('VLC için altyazıyla dil öğrenme yardımcısı'), style='Muted.TLabel').pack(anchor='w')
        right = ttk.Frame(head)
        right.pack(side='right', anchor='n')
        self.pill = tk.Label(right, text=_('●  VLC aranıyor'), bg=CARD2, fg=MUTED, padx=12, pady=6,
                             font=(FONT, 9, 'bold'))
        self.pill.pack(anchor='e')
        self.ui_choices = [('auto', _('Otomatik (sistem dili)')), ('tr', 'Türkçe'), ('en', 'English')]
        self.ui_var = tk.StringVar(value=dict(self.ui_choices).get(self.settings['ui_lang']))
        ui = ttk.Combobox(right, textvariable=self.ui_var, state='readonly', width=28,
                          values=[lbl for code, lbl in self.ui_choices])
        ui.pack(anchor='e', pady=(8, 0))
        ui.bind('<<ComboboxSelected>>', lambda e: self._ui_lang_chosen())

        nb = ttk.Notebook(root)
        nb.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        home = ttk.Frame(nb, style='Card.TFrame', padding=4)
        look = ttk.Frame(nb, style='Card.TFrame', padding=4)
        trans = ttk.Frame(nb, style='Card.TFrame', padding=4)
        conn = ttk.Frame(nb, style='Card.TFrame', padding=4)
        nb.add(home, text=_('Ana sayfa'))
        nb.add(look, text=_('Görünüm'))
        nb.add(trans, text=_('Çeviri'))
        nb.add(conn, text=_('Bağlantı'))
        self._build_home(home)
        self._build_look(look)
        self._build_translation(trans)
        self._build_conn(conn)

    def _build_home(self, parent):
        outer, c = theme.card(parent, _('Şu an oynatılan'))
        outer.pack(fill='x')
        self.detail_var = tk.StringVar(value='')
        self.media_var = tk.StringVar(value='Video: —')
        self.sub_var = tk.StringVar(value=_('Altyazı: —'))
        self.detail_lbl = ttk.Label(c, textvariable=self.detail_var, style='Card.TLabel', wraplength=560,
                                    foreground=theme.ERR, justify='left')
        ttk.Label(c, textvariable=self.media_var, style='Card.TLabel', wraplength=560).pack(anchor='w')
        ttk.Label(c, textvariable=self.sub_var, style='CardMuted.TLabel', wraplength=560).pack(anchor='w', pady=(2, 0))
        ttk.Button(c, text=_('Altyazı dosyası seç…'), command=self.choose_subs).pack(anchor='w', pady=(10, 0))

        outer, c = theme.card(parent, _('Kelimelerin'))
        outer.pack(fill='x', pady=(8, 0))
        tiles = ttk.Frame(c, style='Card.TFrame')
        tiles.pack(fill='x')
        self.stat_lbls = {}
        for i, (k, text, color) in enumerate((('green', _('biliyorum'), COLORS['green']),
                                              ('yellow', _('öğreniyorum'), COLORS['yellow']),
                                              ('red', _('bilmiyorum'), COLORS['red']),
                                              ('fav', _('favori'), FAV))):
            tile = tk.Frame(tiles, bg=CARD2, padx=14, pady=10)
            tile.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 8, 0))
            tiles.columnconfigure(i, weight=1)
            num = tk.Label(tile, text='0', fg=color, bg=CARD2, font=(FONT, 20, 'bold'))
            num.pack(anchor='w')
            tk.Label(tile, text=('★ ' if k == 'fav' else '● ') + text, fg=MUTED, bg=CARD2,
                     font=(FONT, 9)).pack(anchor='w')
            self.stat_lbls[k] = num
        ttk.Button(c, text=_('★  Kelimelerim / Favoriler'), style='Accent.TButton',
                   command=self.open_words).pack(anchor='w', pady=(12, 0))

        outer, c = theme.card(parent, _('Davranış'))
        outer.pack(fill='x', pady=(8, 0))
        self.pause_var = tk.BooleanVar(value=self.settings['pause_on_hover'])
        ttk.Checkbutton(c, text=_('Kelimenin üzerine gelince videoyu duraklat'), variable=self.pause_var,
                        command=lambda: self._set('pause_on_hover', self.pause_var.get())).pack(anchor='w')
        self.hide_var = tk.BooleanVar(value=self.settings['hide_vlc_subs'])
        ttk.Checkbutton(c, text=_("VLC'nin kendi altyazısını kapat (çift görünmesin)"), variable=self.hide_var,
                        command=lambda: self._set('hide_vlc_subs', self.hide_var.get())).pack(anchor='w')
        ttk.Label(c, style='CardMuted.TLabel', wraplength=560, justify='left', text=(
            _('Kelimenin üzerine gel → çevirisi çıkar. Biliyorum / Öğreniyorum / Bilmiyorum ile '
            'renklendir, ☆ ile favorile. Favoriler altı çizili görünür.'))).pack(anchor='w', pady=(8, 0))

    def _build_look(self, parent):
        outer, c = theme.card(parent)
        outer.pack(fill='x')
        self.preview = Preview(c, self, int(600 * self.ui), int(210 * self.ui))
        self.preview.canvas.pack()

        cols = ttk.Frame(parent, style='Card.TFrame')
        cols.pack(fill='both', expand=True, pady=(8, 0))
        cols.columnconfigure(0, weight=1, uniform='col')
        cols.columnconfigure(1, weight=1, uniform='col')
        self.style_vars = {}

        outer, c = theme.card(cols, _('Yazı'))
        outer.grid(row=0, column=0, sticky='nsew', padx=(0, 4))
        c.columnconfigure(1, weight=1)
        ttk.Label(c, text=_('Yazı tipi'), style='Card.TLabel').grid(row=0, column=0, sticky='w', pady=4)
        families = sorted({f for f in tkfont.families() if not f.startswith('@')}, key=str.lower)
        popular = [f for f in POPULAR_FONTS if f in families]
        self.font_var = tk.StringVar(value=self.settings['font_family'])
        fcb = ttk.Combobox(c, textvariable=self.font_var, state='readonly', height=18,
                           values=popular + ['──────────'] + [f for f in families if f not in popular])
        fcb.grid(row=0, column=1, columnspan=2, sticky='ew', pady=4)
        fcb.bind('<<ComboboxSelected>>', self._font_chosen)
        self._slider(c, 1, _('Boyut'), 'font_size', 14, 64, '{} pt')
        ttk.Label(c, text=_('Renk'), style='Card.TLabel').grid(row=2, column=0, sticky='w', pady=6)
        row = ttk.Frame(c, style='Card.TFrame')
        row.grid(row=2, column=1, columnspan=2, sticky='w', pady=6)
        self.text_swatch = theme.swatch(row, self.settings['text_color'], lambda: self._pick_color('text_color'))
        self.text_swatch.pack(side='left')
        self._check(c, 3, _('Kalın'), 'bold')
        self._check(c, 4, _('Siyah kenarlık (açık sahnelerde okunur)'), 'outline')

        outer, c = theme.card(cols, _('Arka plan ve konum'))
        outer.grid(row=0, column=1, sticky='nsew', padx=(4, 0))
        c.columnconfigure(1, weight=1)
        ttk.Label(c, text=_('Renk'), style='Card.TLabel').grid(row=0, column=0, sticky='w', pady=6)
        row = ttk.Frame(c, style='Card.TFrame')
        row.grid(row=0, column=1, columnspan=2, sticky='w', pady=6)
        self.bg_swatch = theme.swatch(row, self.settings['bg_color'], lambda: self._pick_color('bg_color'))
        self.bg_swatch.pack(side='left')
        self._slider(c, 1, _('Opaklık'), 'bg_opacity', 0, 100, '%{}')
        self._check(c, 2, _('Yuvarlak köşeler'), 'rounded')
        self._slider(c, 3, _('Alttan'), 'bottom_pct', 0, 60, '%{}')
        self._slider(c, 4, _('Genişlik'), 'max_width_pct', 40, 100, '%{}')

        ttk.Button(parent, text=_('Varsayılanlara dön'), command=self._reset_style).pack(anchor='e', pady=(8, 0))

    def _slider(self, parent, row, label, key, lo, hi, fmt):
        ttk.Label(parent, text=label, style='Card.TLabel').grid(row=row, column=0, sticky='w', pady=6, padx=(0, 10))
        val = ttk.Label(parent, text=fmt.format(self.settings[key]), style='CardMuted.TLabel', width=6, anchor='e')
        var = tk.DoubleVar(value=self.settings[key])

        def changed(v):
            v = int(round(float(v)))
            val.configure(text=fmt.format(v))
            if v != self.settings[key]:
                self.settings[key] = v
                self._style_changed()
        ttk.Scale(parent, from_=lo, to=hi, variable=var, command=changed).grid(row=row, column=1, sticky='ew', pady=6)
        val.grid(row=row, column=2, sticky='e', padx=(8, 0))
        self.style_vars[key] = (var, val, fmt)

    def _check(self, parent, row, label, key):
        var = tk.BooleanVar(value=self.settings[key])

        def changed():
            self.settings[key] = var.get()
            self._style_changed()
        ttk.Checkbutton(parent, text=label, variable=var, command=changed).grid(
            row=row, column=0, columnspan=3, sticky='w', pady=3)
        self.style_vars[key] = (var, None, None)

    def _font_chosen(self, _event):
        fam = self.font_var.get()
        if fam.startswith('──'):
            self.font_var.set(self.settings['font_family'])
            return
        self.settings['font_family'] = fam
        self._style_changed()

    def _pick_color(self, key):
        hex_color = colorchooser.askcolor(color=self.settings[key], parent=self.root,
                                             title=_('Renk seç'))[1]
        if hex_color:
            self.settings[key] = hex_color
            (self.text_swatch if key == 'text_color' else self.bg_swatch).configure(bg=hex_color)
            self._style_changed()

    def _reset_style(self):
        self.settings.update(Settings.STYLE_DEFAULTS)
        for key, (var, val, fmt) in self.style_vars.items():
            var.set(self.settings[key])
            if val is not None:
                val.configure(text=fmt.format(self.settings[key]))
        self.font_var.set(self.settings['font_family'])
        self.text_swatch.configure(bg=self.settings['text_color'])
        self.bg_swatch.configure(bg=self.settings['bg_color'])
        self._style_changed()

    def _style_changed(self):
        self.preview.render()
        if self._style_job:
            self.root.after_cancel(self._style_job)
        self._style_job = self.root.after(120, self._apply_style)

    def _apply_style(self):
        self._style_job = None
        self.settings.save()
        self.overlay.update_style()

    def _build_translation(self, parent):
        outer, c = theme.card(parent, _('Diller'), (
            _('Altyazı dili: videodaki (öğrendiğin) dil. Çeviri dili: kelimelerin hangi dile çevrileceği.')))
        outer.pack(fill='x')
        self.src_choices = languages.choices(with_auto=True)
        self.tgt_choices = languages.choices()
        ttk.Label(c, text=_('Altyazı dili'), style='Card.TLabel').grid(row=0, column=0, sticky='w', pady=4)
        self.src_var = tk.StringVar(value=dict(self.src_choices).get(self.settings['source_lang'], ''))
        src = ttk.Combobox(c, textvariable=self.src_var, state='readonly', height=18, width=30,
                           values=[lbl for code, lbl in self.src_choices])
        src.grid(row=0, column=1, sticky='w', padx=10, pady=4)
        ttk.Label(c, text=_('Çeviri dili'), style='Card.TLabel').grid(row=1, column=0, sticky='w', pady=4)
        self.tgt_var = tk.StringVar(value=dict(self.tgt_choices).get(self.settings['target_lang'], ''))
        tgt = ttk.Combobox(c, textvariable=self.tgt_var, state='readonly', height=18, width=30,
                           values=[lbl for code, lbl in self.tgt_choices])
        tgt.grid(row=1, column=1, sticky='w', padx=10, pady=4)
        ttk.Button(c, text=_('⇄  Yer değiştir'), command=self._swap_langs).grid(row=0, column=2, rowspan=2)
        src.bind('<<ComboboxSelected>>', lambda e: self._langs_chosen())
        tgt.bind('<<ComboboxSelected>>', lambda e: self._langs_chosen())

        outer, c = theme.card(parent, _('Çeviri servisi'), (
            _('Kendi API anahtarını kullan. Anahtar sadece bu bilgisayarda (data/ayarlar.json) '
            'saklanır ve sadece seçtiğin servise gönderilir.')))
        outer.pack(fill='x', pady=(8, 0))
        self.provider_var = tk.StringVar(value=self.settings['provider'])
        for value, text in (('deepl', _('DeepL API (Free ya da Pro anahtarı)')),
                            ('google', 'Google Cloud Translation API'),
                            ('free', _('Anahtarsız (resmi değil, sınırlı, her an bozulabilir; sadece denemek için)'))):
            ttk.Radiobutton(c, text=text, value=value, variable=self.provider_var,
                            command=self._provider_chosen).pack(anchor='w', pady=2)
        row = ttk.Frame(c, style='Card.TFrame')
        row.pack(fill='x', pady=(10, 0))
        ttk.Label(row, text=_('API anahtarı'), style='Card.TLabel').pack(side='left')
        self.key_var = tk.StringVar()
        self.key_entry = ttk.Entry(row, textvariable=self.key_var, width=46, show='•')
        self.key_entry.pack(side='left', padx=10)
        ttk.Button(row, text=_('Kaydet'), command=self._save_key).pack(side='left')
        ttk.Button(row, text=_('Test et'), style='Accent.TButton',
                   command=self._test_translation).pack(side='left', padx=(8, 0))
        self.trans_status = tk.StringVar()
        ttk.Label(c, textvariable=self.trans_status, style='CardMuted.TLabel', wraplength=560,
                  justify='left').pack(anchor='w', pady=(8, 0))
        ttk.Label(c, style='CardMuted.TLabel', wraplength=560, justify='left', text=(
            _('Anahtar nasıl alınır? README.tr.md içindeki "Çeviri servisi ve API anahtarı" '
            'bölümüne bak.'))).pack(anchor='w', pady=(4, 0))
        self._provider_chosen(save=False)

    def _ui_lang_chosen(self):
        code = next(c for c, lbl in self.ui_choices if lbl == self.ui_var.get())
        if code == self.settings['ui_lang']:
            return
        self._set('ui_lang', code)
        new = code if code in i18n.UI_LANGS else i18n.system_lang()
        if new != i18n.current() and messagebox.askyesno(
                APP_NAME, _('Arayüz dili değişti. Program şimdi yeniden başlatılsın mı?')):
            self.restart = True
            self.quit()

    def lang_pair(self):
        return '%s>%s' % (self.settings['source_lang'], self.settings['target_lang'])

    def translate_opts(self):
        """translate_word / translate_sentence için (kaynak, hedef, servis, anahtar)."""
        s = self.settings
        provider = s['provider']
        key = s.get(provider + '_key', '') if provider in ('deepl', 'google') else ''
        return s['source_lang'], s['target_lang'], provider, key.strip()

    def _langs_chosen(self):
        src = next(c for c, l in self.src_choices if l == self.src_var.get())
        tgt = next(c for c, l in self.tgt_choices if l == self.tgt_var.get())
        if (src, tgt) == (self.settings['source_lang'], self.settings['target_lang']):
            return
        old_src = self.settings['source_lang']
        self.settings['source_lang'], self.settings['target_lang'] = src, tgt
        self.settings.save()
        self.trans_status.set('')
        self.overlay.popup.hide()
        if src != old_src and self.media_uri and self.load_token is not None:
            self._on_media(self.media_uri)  # yeni dile uygun altyazıyı ara

    def _swap_langs(self):
        if self.settings['source_lang'] == languages.AUTO:
            messagebox.showinfo(APP_NAME, _('Altyazı dili "Otomatik algıla" iken yer değiştirilemez.'))
            return
        a, b = self.src_var.get(), self.tgt_var.get()
        self.src_var.set(b)
        self.tgt_var.set(a)
        self._langs_chosen()

    def _provider_chosen(self, save=True):
        p = self.provider_var.get()
        keyed = p in ('deepl', 'google')
        self.key_var.set(self.settings.get(p + '_key', '') if keyed else '')
        self.key_entry.configure(state='normal' if keyed else 'disabled')
        self.trans_status.set('')
        if save:
            self._set('provider', p)
            self.overlay.popup.hide()

    def _save_key(self):
        p = self.provider_var.get()
        if p in ('deepl', 'google'):
            self._set(p + '_key', self.key_var.get().strip())
            self.trans_status.set(_('Anahtar kaydedildi.'))

    def _test_translation(self):
        self._save_key()
        tgt, provider, key = self.translate_opts()[1:]
        sample = 'Merhaba dostum, nasılsın?' if tgt == 'en' else 'Hello my friend, how are you?'
        self.trans_status.set(_('Deneniyor…'))

        def done(res, err):
            if err is None:
                self.trans_status.set(_('✓ Çalışıyor: "%s" → "%s"') % (sample, res))
            else:
                self.trans_status.set('✕ ' + (str(err) if isinstance(err, TranslateError)
                                              else _('Çeviri alınamadı (internet?)')))
        self.run_bg(lambda: translate_sentence(sample, 'auto', tgt, provider, key), done)

    def _build_conn(self, parent):
        outer, c = theme.card(parent, _('VLC bağlantısı'), (
            _("Program VLC'ye, VLC'nin web arayüzü üzerinden (sadece bu bilgisayardan, şifreyle) "
            'bağlanır. İlk kurulumda "VLC\'yi otomatik ayarla" yeterli.')))
        outer.pack(fill='x')
        ttk.Label(c, text='Port', style='Card.TLabel').grid(row=0, column=0, sticky='w', pady=6)
        self.port_var = tk.StringVar(value=str(self.settings['port']))
        ttk.Entry(c, textvariable=self.port_var, width=8).grid(row=0, column=1, sticky='w', padx=(10, 20))
        ttk.Label(c, text=_('Şifre'), style='Card.TLabel').grid(row=0, column=2, sticky='w')
        self.pw_var = tk.StringVar(value=self.settings['password'])
        ttk.Entry(c, textvariable=self.pw_var, width=20, show='•').grid(row=0, column=3, sticky='w', padx=10)
        row = ttk.Frame(c, style='Card.TFrame')
        row.grid(row=1, column=0, columnspan=4, sticky='w', pady=(12, 0))
        ttk.Button(row, text=_('Kaydet'), command=self._save_conn).pack(side='left')
        ttk.Button(row, text=_("VLC'yi otomatik ayarla"), style='Accent.TButton',
                   command=self.configure_vlc).pack(side='left', padx=8)

    def _set(self, key, value):
        self.settings[key] = value
        self.settings.save()

    def _save_conn(self):
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror(APP_NAME, _('Port bir sayı olmalı.'))
            return
        self.settings['port'] = port
        self.settings['password'] = self.pw_var.get()
        self.settings.save()

    def _on_store_change(self):
        counts = self.store.counts()
        for k, lbl in self.stat_lbls.items():
            lbl.configure(text=str(counts[k]))
        if hasattr(self, 'overlay'):
            self.overlay.refresh_styles()
            self.overlay.popup.render()

    def _set_conn(self, conn):
        self.conn = conn
        pill = {'ok': (_('●  Bağlı'), theme.OK, '#173323'),
                'auth': (_('●  Şifre yanlış'), theme.ERR, '#3a1c1f'),
                'other': (_('●  Port dolu'), theme.ERR, '#3a1c1f')}.get(conn, (_('●  VLC bulunamadı'), theme.ERR, '#3a1c1f'))
        self.pill.configure(text=pill[0], fg=pill[1], bg=pill[2])
        detail = {
            'ok': '',
            'auth': _('Şifre yanlış. "Bağlantı" sekmesinden "VLC\'yi otomatik ayarla"ya bas.'),
            'other': (_('Port %s başka bir program tarafından kullanılıyor. VLC\'yi kapatıp "Bağlantı" '
                      'sekmesinden "VLC\'yi otomatik ayarla"ya bas, boş bir port seçilecek.') % self.settings['port']),
        }.get(conn, _('VLC açık değil ya da web arayüzü kapalı. İlk kez kullanıyorsan "Bağlantı" sekmesinden '
                    '"VLC\'yi otomatik ayarla"ya bas.'))
        self.detail_var.set(detail)
        if detail:
            self.detail_lbl.pack(anchor='w', pady=(0, 6), before=self.detail_lbl.master.winfo_children()[1])
        else:
            self.detail_lbl.pack_forget()
        if conn != 'ok':
            self.media_var.set('Video: —')
            self.sub_var.set(_('Altyazı: —'))
            self.subs = None

    def open_words(self):
        if self.words_window:
            self.words_window.win.lift()
            self.words_window.win.focus_force()
        else:
            self.words_window = WordsWindow(self)

    # -- VLC ayarı -----------------------------------------------------
    def _first_run(self):
        if self.settings['password']:
            return
        if messagebox.askyesno(APP_NAME, (
                _('Bu programın VLC ile konuşabilmesi için VLC\'nin web arayüzünün açılması gerekiyor '
                '(sadece bu bilgisayardan erişilebilir, şifreli).\n\n'
                'VLC ayarlarını şimdi otomatik yapayım mı?'))):
            self.configure_vlc()

    def configure_vlc(self):
        while vlc_setup.vlc_running():
            if not messagebox.askretrycancel(APP_NAME, _("Ayarları yazabilmem için önce VLC'yi tamamen kapat, "
                                                       "sonra 'Yeniden dene'ye bas.")):
                return
        self._save_conn()
        self.settings['port'] = vlc_setup.pick_port(self.settings['port'])
        self.port_var.set(str(self.settings['port']))
        pw = self.settings['password'] or secrets.token_urlsafe(9)
        try:
            vlc_setup.configure(pw, self.settings['port'])
        except OSError as e:
            messagebox.showerror(APP_NAME, _('VLC ayar dosyası yazılamadı:\n%s') % e)
            return
        self.settings['password'] = pw
        self.settings.save()
        self.pw_var.set(pw)
        messagebox.showinfo(APP_NAME, _("VLC ayarlandı ✓\n\nŞimdi VLC'yi açıp altyazılı videonu başlat. "
                                      'Bu pencere açık kalsın.'))

    # -- arka plan işleri ----------------------------------------------
    def post(self, fn, *args):
        self.q.put((fn, args))

    def run_bg(self, func, callback):
        def work():
            try:
                res, err = func(), None
            except Exception as e:  # noqa: BLE001
                res, err = None, e
            self.post(callback, res, err)
        threading.Thread(target=work, daemon=True).start()

    def client(self):
        return VLCClient(self.settings['port'], self.settings['password'])

    def vlc_cmd(self, command, **params):
        def work():
            try:
                self.client().command(command, **params)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _poll_loop(self):
        last_plid, conn, last_hide = None, None, 0.0
        while not self.stopping:
            client = self.client()
            try:
                st = client.status()
                self.clock.update(st)
                self.vlc_state = st.get('state') or 'stopped'
                new_conn = 'ok'
                # VLC altyazıyı (özellikle yanındaki dosyayı) gecikmeli açabiliyor;
                # bizim altyazımız yüklüyken onunkini düzenli olarak kapalı tut.
                if self.subs and self.settings['hide_vlc_subs'] and time.monotonic() - last_hide > 2:
                    last_hide = time.monotonic()
                    client.command('subtitle_track', val=-1)
                plid = st.get('currentplid')
                if plid != last_plid:
                    last_plid = plid
                    uri = client.current_uri() if plid not in (None, -1) else None
                    self.post(self._on_media, uri)
            except VLCAuthError:
                new_conn, last_plid = 'auth', None
            except urllib.error.HTTPError:
                new_conn, last_plid = 'other', None  # portta VLC değil başka bir program var
            except Exception:
                new_conn, last_plid = 'down', None
            if new_conn != conn:
                conn = new_conn
                self.post(self._set_conn, conn)
            time.sleep(0.15)

    def _pump(self):
        while True:
            try:
                fn, args = self.q.get_nowait()
            except queue.Empty:
                return
            try:
                fn(*args)
            except Exception:
                log_error(*sys.exc_info())

    def _tick(self):
        self._pump()
        text = ''
        if self.subs and self.conn == 'ok' and self.vlc_state in ('playing', 'paused'):
            text = self.subs.at(self.clock.now())
        self.overlay.set_text(text)
        self.overlay.poll_pointer()
        self.root.after(40, self._tick)

    def _follow(self):
        try:
            self.overlay.follow(osutil.find_vlc())
        except Exception:
            log_error(*sys.exc_info())
        self.root.after(250, self._follow)

    # -- altyazı -------------------------------------------------------
    def _on_media(self, uri):
        self.subs = None
        self.load_token = token = object()
        self.media_uri = uri
        path = self.media_path = uri_to_path(uri)
        if not uri:
            self.media_var.set('Video: —')
            self.sub_var.set(_('Altyazı: —'))
            return
        self.media_var.set('Video: ' + (os.path.basename(path) if path else uri))
        if not path:
            self.sub_var.set(_('Altyazı: video yerel bir dosya değil — "Altyazı dosyası seç" ile seç'))
            return
        self.sub_var.set(_('Altyazı: aranıyor…'))

        langs = self.settings['source_lang'], self.settings['target_lang']

        def work():
            found = find_external(path, *langs)
            if found:
                return found, os.path.basename(found)
            self.post(self.sub_var.set, _('Altyazı: videonun içindeki altyazı çıkarılıyor (biraz sürebilir)…'))
            return extract_embedded(path, os.path.join(DATA_DIR, 'cache'), *langs)

        def done(res, err):
            if token is not self.load_token:
                return
            if err or not res:
                self.sub_var.set(_('Altyazı bulunamadı — "Altyazı dosyası seç" ile .srt dosyasını seç'))
            else:
                self.load_subs(*res)
        self.run_bg(work, done)

    def load_subs(self, path, label=None):
        try:
            subs = Subtitles.load(path)
        except Exception as e:
            self.sub_var.set(_('Altyazı okunamadı: %s') % e)
            return
        if not subs.cues:
            self.sub_var.set(_('Altyazı dosyası boş ya da tanınmadı: ') + os.path.basename(path))
            return
        self.subs = subs
        self.sub_var.set(_('Altyazı: %s (%d satır)') % (label or os.path.basename(path), len(subs.cues)))

    def choose_subs(self):
        path = filedialog.askopenfilename(
            title=_('Altyazı dosyası seç'),
            initialdir=os.path.dirname(self.media_path) if self.media_path else None,
            filetypes=[(_('Altyazı'), '*.srt *.vtt *.ass *.ssa'), (_('Tüm dosyalar'), '*.*')])
        if path:
            self.load_token = None
            self.load_subs(path)

    # -- fareyle durdurma ----------------------------------------------
    def pause_for_hover(self):
        if self.settings['pause_on_hover'] and self.vlc_state == 'playing':
            self.hover_paused = True
            self.clock.stop_now()
            self.vlc_cmd('pl_forcepause')

    def resume_after_hover(self):
        if self.hover_paused:
            self.hover_paused = False
            self.vlc_cmd('pl_forceresume')

    def quit(self):
        self.stopping = True
        if self.hover_paused:
            try:
                self.client().command('pl_forceresume')
            except Exception:
                pass
        self.settings.save()
        self.root.destroy()


def main():
    sys.excepthook = log_error
    app = App()
    app.root.mainloop()
    if app.restart:
        subprocess.Popen([sys.executable, os.path.abspath(__file__)] + sys.argv[1:])


if __name__ == '__main__':
    main()
