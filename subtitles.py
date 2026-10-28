"""Altyazı dosyası okuma (SRT / VTT / ASS) ve video için altyazı bulma."""
import bisect
import hashlib
import json
import os
import re
import shutil
import subprocess

import languages
from i18n import _

SUB_EXTS = ('.srt', '.vtt', '.ass', '.ssa')
TEXT_CODECS = {'subrip', 'srt', 'ass', 'ssa', 'webvtt', 'mov_text', 'text'}
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

_TS = re.compile(r'(?:(\d+):)?(\d{1,2}):(\d{2})[,.](\d{1,3})')
_TAG = re.compile(r'<[^>]*>|\{[^}]*\}')


def _secs(m):
    h, mn, s, frac = m.groups()
    return int(h or 0) * 3600 + int(mn) * 60 + int(s) + int(frac.ljust(3, '0')) / 1000


def _read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        return raw.decode('utf-16')
    for enc in ('utf-8-sig', 'cp1254', 'cp1252'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode('latin-1', 'replace')


def _clean(text):
    text = text.replace('\\N', '\n').replace('\\n', '\n').replace('\\h', ' ')
    text = _TAG.sub('', text)
    lines = (l.strip() for l in text.split('\n'))
    return '\n'.join(l for l in lines if l)


def _parse_srt_vtt(text):
    cues = []
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    for block in re.split(r'\n\s*\n', text):
        lines = block.strip('\n').split('\n')
        for i, line in enumerate(lines):
            if '-->' not in line:
                continue
            a, b = line.split('-->', 1)
            ma, mb = _TS.search(a), _TS.search(b)
            if ma and mb:
                body = _clean('\n'.join(lines[i + 1:]))
                if body:
                    cues.append((_secs(ma), _secs(mb), body))
            break
    return cues


def _parse_ass(text):
    cues = []
    for line in text.splitlines():
        if not line.startswith('Dialogue:'):
            continue
        parts = line[len('Dialogue:'):].split(',', 9)
        if len(parts) < 10:
            continue
        ma, mb = _TS.search(parts[1]), _TS.search(parts[2])
        body = _clean(parts[9])
        if ma and mb and body:
            cues.append((_secs(ma), _secs(mb), body))
    return cues


class Subtitles:
    def __init__(self, cues):
        self.cues = sorted(cues)
        self.starts = [c[0] for c in self.cues]

    @classmethod
    def load(cls, path):
        text = _read_text(path)
        if path.lower().endswith(('.ass', '.ssa')) or '[Events]' in text:
            return cls(_parse_ass(text))
        return cls(_parse_srt_vtt(text))

    def at(self, t):
        """t saniyesinde ekranda olması gereken altyazı metni."""
        i = bisect.bisect_right(self.starts, t)
        out = []
        for s, e, body in self.cues[max(0, i - 8):i]:
            if s <= t < e and body not in out:
                out.append(body)
        return '\n'.join(out)


def _tokens(filename):
    return set(re.split(r'[._\-\s\[\]()]+', filename.lower()))


def _name_score(filename, stem, want):
    tokens = _tokens(filename)
    score = 0
    if os.path.splitext(filename)[0].lower() == stem:
        score += 1
    if tokens & want:
        score += 2
    if 'forced' in tokens:
        score -= 2
    return score


def find_external(media_path, source='en', target='tr'):
    """Videonun yanındaki (veya Subs klasöründeki) altyazı dosyasını bulur.

    Adında `source` dili geçen dosyayı tercih eder, `target` (çeviri) dilindekileri atlar.
    """
    want, skip = languages.tokens(source), languages.tokens(target) - languages.tokens(source)
    folder, base = os.path.split(media_path)
    stem = os.path.splitext(base)[0].lower()
    seen, matches, all_subs = set(), [], []
    for d in (folder, os.path.join(folder, 'Subs'), os.path.join(folder, 'Subtitles')):
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            p = os.path.join(d, name)
            if not name.lower().endswith(SUB_EXTS) or p.lower() in seen:
                continue
            seen.add(p.lower())
            if _tokens(name) & skip:
                continue  # çeviri dilindeki altyazıyı değil, öğrenilen dildekini arıyoruz
            all_subs.append(p)
            if name.lower().startswith(stem):
                matches.append(p)
    pool = matches or (all_subs if len(all_subs) == 1 else [])
    if not pool:
        return None
    return max(pool, key=lambda p: _name_score(os.path.basename(p), stem, want))


def extract_embedded(media_path, cache_dir, source='en', target='tr'):
    """Video içindeki (mkv/mp4) metin altyazıyı ffmpeg ile .srt olarak çıkarır.

    (srt_yolu, etiket) veya None döner.
    """
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    if not ffmpeg or not ffprobe or not os.path.isfile(media_path):
        return None
    probe = subprocess.run(
        [ffprobe, '-v', 'error', '-select_streams', 's',
         '-show_entries', 'stream=index,codec_name:stream_tags=language,title',
         '-of', 'json', media_path],
        capture_output=True, timeout=60, creationflags=_NO_WINDOW)
    streams = json.loads(probe.stdout or b'{}').get('streams', [])
    streams = [s for s in streams if s.get('codec_name') in TEXT_CODECS]
    if not streams:
        return None

    want, skip = languages.tokens(source), languages.tokens(target) - languages.tokens(source)

    def rank(s):
        tags = s.get('tags') or {}
        lang = (tags.get('language') or '').lower()
        title = (tags.get('title') or '').lower()
        score = 3 if lang in want else -5 if lang in skip else 0
        if 'forced' in title:
            score -= 2
        return score

    best = max(streams, key=rank)
    tags = best.get('tags') or {}
    label = _('gömülü altyazı (%s)') % (tags.get('title') or tags.get('language') or best['index'])
    key = hashlib.md5(('%s|%d|%d' % (media_path, os.path.getsize(media_path), best['index']))
                      .encode('utf-8')).hexdigest()
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, key + '.srt')
    if not os.path.isfile(dest):
        tmp = dest + '.part.srt'
        subprocess.run(
            [ffmpeg, '-y', '-v', 'error', '-i', media_path,
             '-map', '0:%d' % best['index'], '-c:s', 'srt', tmp],
            capture_output=True, timeout=900, creationflags=_NO_WINDOW)
        if not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
            return None
        os.replace(tmp, dest)
    return dest, label
