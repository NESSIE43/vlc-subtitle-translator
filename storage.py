"""Kelimeler, çeviri önbelleği ve ayarlar için JSON tabanlı kalıcı depolama."""
import datetime
import json
import os
import re
import sys
from contextlib import contextmanager

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

_APOS = str.maketrans({'’': "'", '‘': "'", '`': "'", 'İ': 'i'})


def normalize(token):
    """Altyazıdaki bir parçayı sözlük anahtarına çevirir ("Don't," -> "don't")."""
    w = token.translate(_APOS).lower()
    w = re.sub(r"^\W+|\W+$", '', w)
    if not re.search(r'[^\W\d_]', w):  # en az bir harf (her alfabede)
        return ''
    return w


def _load(path, default):
    try:
        with open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


class Settings(dict):
    DEFAULTS = {
        'ui_lang': 'auto',
        'port': 8765,
        'password': '',
        'pause_on_hover': True,
        'hide_vlc_subs': True,
        'source_lang': 'en',
        'target_lang': 'tr',
        'provider': 'free',
        'deepl_key': '',
        'google_key': '',
    }
    # altyazı görünümü ("Varsayılanlara dön" sadece bunları sıfırlar)
    STYLE_DEFAULTS = {
        'font_family': 'Segoe UI' if sys.platform == 'win32' else 'DejaVu Sans',
        'font_size': 26,
        'bold': True,
        'text_color': '#ffffff',
        'outline': True,
        'bg_color': '#000000',
        'bg_opacity': 55,
        'rounded': True,
        'bottom_pct': 12,
        'max_width_pct': 80,
    }
    DEFAULTS.update(STYLE_DEFAULTS)

    def __init__(self):
        self.path = os.path.join(DATA_DIR, 'ayarlar.json')
        super().__init__(self.DEFAULTS)
        self.update(_load(self.path, {}))

    def save(self):
        _save(self.path, dict(self))


class TranslationCache:
    """data["en>tr"][kelime] = {main, alts}"""

    def __init__(self):
        self.path = os.path.join(DATA_DIR, 'ceviri_onbellek.json')
        data = _load(self.path, {})
        if any(isinstance(v, dict) and 'main' in v for v in data.values()):
            data = {'en>tr': data}  # eski (sadece İngilizce -> Türkçe) önbellek
        self.data = data

    def get(self, pair, word):
        return self.data.get(pair, {}).get(word)

    def put(self, pair, word, result):
        self.data.setdefault(pair, {})[word] = result
        _save(self.path, self.data)


class WordStore:
    """Renklendirilmiş / favorilenmiş kelimeler.

    words[kelime] = {color: None|'green'|'yellow'|'red', fav: bool,
                     tr: str, example: str, added: str}
    """

    def __init__(self):
        self.path = os.path.join(DATA_DIR, 'kelimeler.json')
        self.words = _load(self.path, {})
        self.listeners = []
        self._depth = 0
        self._dirty = False

    def get(self, w):
        return self.words.get(w)

    def color(self, w):
        e = self.words.get(w)
        return e.get('color') if e else None

    def is_fav(self, w):
        e = self.words.get(w)
        return bool(e and e.get('fav'))

    def _entry(self, w, tr=None, example=None):
        e = self.words.setdefault(w, {
            'color': None, 'fav': False, 'tr': '', 'example': '',
            'added': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        })
        if tr and not e.get('tr'):
            e['tr'] = tr
        if example and not e.get('example'):
            e['example'] = example
        return e

    def _cleanup(self, w):
        e = self.words.get(w)
        if e and not e.get('color') and not e.get('fav'):
            del self.words[w]

    def set_color(self, w, color, tr=None, example=None):
        self._entry(w, tr, example)['color'] = color
        self._cleanup(w)
        self._changed()

    def toggle_fav(self, w, tr=None, example=None):
        e = self._entry(w, tr, example)
        e['fav'] = not e.get('fav')
        self._cleanup(w)
        self._changed()

    def set_fav(self, w, fav):
        self._entry(w)['fav'] = fav
        self._cleanup(w)
        self._changed()

    def set_translation(self, w, tr):
        if w in self.words:
            self.words[w]['tr'] = tr
            self._changed()

    def remove(self, w):
        if self.words.pop(w, None) is not None:
            self._changed()

    def counts(self):
        c = {'green': 0, 'yellow': 0, 'red': 0, 'fav': 0}
        for e in self.words.values():
            if e.get('color') in c:
                c[e['color']] += 1
            if e.get('fav'):
                c['fav'] += 1
        return c

    @contextmanager
    def batch(self):
        """Birden çok değişikliği tek kayıtta toplar."""
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
            if self._depth == 0 and self._dirty:
                self._flush()

    def _changed(self):
        self._dirty = True
        if self._depth == 0:
            self._flush()

    def _flush(self):
        self._dirty = False
        _save(self.path, self.words)
        for cb in list(self.listeners):
            cb()
