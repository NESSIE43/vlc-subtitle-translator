"""Kelimelerim / Favoriler penceresi."""
import csv
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import theme
from i18n import _
from theme import COLORS, LABELS

APP_NAME = _('VLC Altyazı Çevirmeni')


class WordsWindow:
    FILTERS = [('fav', _('★  Favoriler')), ('all', _('Tüm kelimeler')), ('green', _('●  Biliyorum')),
               ('yellow', _('●  Öğreniyorum')), ('red', _('●  Bilmiyorum'))]
    COLUMNS = [('fav', '★', 40), ('word', _('Kelime'), 140), ('tr', _('Çeviri'), 210),
               ('status', _('Durum'), 120), ('example', _('Örnek cümle'), 330), ('added', _('Eklenme'), 125)]

    def __init__(self, app, start_filter='fav'):
        self.app = app
        win = self.win = tk.Toplevel(app.root)
        win.title(_('Kelimelerim'))
        win.geometry('1020x560')
        win.minsize(680, 340)
        theme.window(win)

        top = ttk.Frame(win, padding=(16, 14, 16, 10))
        top.pack(fill='x')
        ttk.Label(top, text=_('Kelimelerim'), style='Title.TLabel').pack(side='left', padx=(0, 18))
        self.filter_var = tk.StringVar(value=dict(self.FILTERS)[start_filter])
        cb = ttk.Combobox(top, textvariable=self.filter_var, state='readonly', width=16,
                          values=[name for key, name in self.FILTERS])
        cb.pack(side='left', padx=(0, 10))
        cb.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *a: self.refresh())
        ttk.Label(top, text=_('Ara'), style='Muted.TLabel').pack(side='left', padx=(6, 4))
        ttk.Entry(top, textvariable=self.search_var, width=24).pack(side='left')
        self.count_var = tk.StringVar()
        ttk.Label(top, textvariable=self.count_var, style='Muted.TLabel').pack(side='right')

        mid = ttk.Frame(win, padding=(16, 0))
        mid.pack(fill='both', expand=True)
        tree = self.tree = ttk.Treeview(mid, columns=[c[0] for c in self.COLUMNS],
                                        show='headings', selectmode='extended')
        self.sort = ('added', True)
        for col, title, width in self.COLUMNS:
            tree.heading(col, text=title, command=lambda c=col: self._sort_by(c))
            tree.column(col, width=width, anchor='center' if col == 'fav' else 'w',
                        stretch=col in ('tr', 'example'))
        for c, color in COLORS.items():
            tree.tag_configure(c, foreground=color)
        sb = ttk.Scrollbar(mid, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        tree.bind('<Double-1>', lambda e: self.edit_translation())
        tree.bind('<Delete>', lambda e: self.delete())

        bot = ttk.Frame(win, padding=16)
        bot.pack(fill='x')
        for c in ('green', 'yellow', 'red'):
            b = tk.Label(bot, text='●  ' + LABELS[c], fg=COLORS[c], bg=theme.CARD2, padx=12, pady=7,
                         font=(theme.FONT, 10, 'bold'), cursor='hand2')
            b.bind('<Button-1>', lambda e, c=c: self.set_color(c))
            b.pack(side='left', padx=(0, 6))
        ttk.Button(bot, text=_('Renksiz'), command=lambda: self.set_color(None)).pack(side='left', padx=(0, 16))
        ttk.Button(bot, text=_('★ Favori'), command=self.toggle_fav).pack(side='left', padx=(0, 6))
        ttk.Button(bot, text=_('Çeviriyi düzenle'), command=self.edit_translation).pack(side='left', padx=(0, 6))
        ttk.Button(bot, text=_('Sil'), command=self.delete).pack(side='left')
        ttk.Button(bot, text=_('CSV olarak dışa aktar'), style='Accent.TButton',
                   command=self.export).pack(side='right')

        app.store.listeners.append(self.refresh)
        win.protocol('WM_DELETE_WINDOW', self.close)
        self.refresh()

    def close(self):
        if self.refresh in self.app.store.listeners:
            self.app.store.listeners.remove(self.refresh)
        self.app.words_window = None
        self.win.destroy()

    def _filter_key(self):
        name = self.filter_var.get()
        return next(k for k, n in self.FILTERS if n == name)

    def _rows(self):
        fk, q = self._filter_key(), self.search_var.get().strip().lower()
        for w, e in self.app.store.words.items():
            if fk == 'fav' and not e.get('fav'):
                continue
            if fk in COLORS and e.get('color') != fk:
                continue
            if q and q not in w and q not in (e.get('tr') or '').lower():
                continue
            yield w, e

    def _values(self, w, e):
        c = e.get('color')
        return {'fav': '★' if e.get('fav') else '', 'word': w, 'tr': e.get('tr') or '',
                'status': ('● ' + LABELS[c]) if c in LABELS else '—',
                'example': e.get('example') or '', 'added': e.get('added') or ''}

    def _sort_by(self, col):
        self.sort = (col, not self.sort[1] if self.sort[0] == col else False)
        self.refresh()

    def refresh(self):
        if not self.win.winfo_exists():
            return
        selected = set(self.tree.selection())
        col, rev = self.sort
        rows = [(w, self._values(w, e), e.get('color')) for w, e in self._rows()]
        rows.sort(key=lambda r: r[1][col].lower(), reverse=rev)
        self.tree.delete(*self.tree.get_children())
        for w, vals, color in rows:
            self.tree.insert('', 'end', iid=w, values=[vals[c[0]] for c in self.COLUMNS],
                             tags=(color,) if color else ())
        keep = [w for w in selected if self.tree.exists(w)]
        if keep:
            self.tree.selection_set(keep)
        total = len(self.app.store.words)
        self.count_var.set(_('%d gösteriliyor · toplam %d kelime') % (len(rows), total))

    def _selection(self):
        sel = list(self.tree.selection())
        if not sel:
            messagebox.showinfo(APP_NAME, _('Önce listeden kelime seç.'), parent=self.win)
        return sel

    def set_color(self, color):
        with self.app.store.batch():
            for w in self._selection():
                self.app.store.set_color(w, color)

    def toggle_fav(self):
        sel = self._selection()
        if sel:
            target = not all(self.app.store.is_fav(w) for w in sel)
            with self.app.store.batch():
                for w in sel:
                    self.app.store.set_fav(w, target)

    def edit_translation(self):
        sel = self._selection()
        if not sel:
            return
        w = sel[0]
        val = simpledialog.askstring(_('Çeviriyi düzenle'), _('"%s" için çeviri:') % w,
                                     initialvalue=self.app.store.get(w).get('tr', ''), parent=self.win)
        if val is not None:
            self.app.store.set_translation(w, val.strip())

    def delete(self):
        sel = self._selection()
        if sel and messagebox.askyesno(APP_NAME, _('%d kelime silinsin mi?') % len(sel), parent=self.win):
            with self.app.store.batch():
                for w in sel:
                    self.app.store.remove(w)

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.win, defaultextension='.csv',
                                            initialfile=_('kelimelerim.csv'),
                                            filetypes=[('CSV', '*.csv')])
        if not path:
            return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            wr = csv.writer(f, delimiter=';')
            wr.writerow([_('Kelime'), _('Çeviri'), _('Durum'), _('Favori'), _('Örnek cümle'), _('Eklenme')])
            for w, e in self._rows():
                v = self._values(w, e)
                wr.writerow([w, v['tr'], LABELS.get(e.get('color'), ''),
                             _('evet') if e.get('fav') else '', v['example'], v['added']])
        messagebox.showinfo(APP_NAME, _('Kaydedildi:\n') + path, parent=self.win)
