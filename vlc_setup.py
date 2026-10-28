"""VLC'nin ayar dosyasında (vlcrc) web arayüzünü açar."""
import os
import re
import shutil
import socket
import subprocess
import sys

_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def _vlcrc():
    if sys.platform == 'win32':
        return os.path.join(os.environ.get('APPDATA', ''), 'vlc', 'vlcrc')
    home = os.path.expanduser('~')
    config = os.environ.get('XDG_CONFIG_HOME') or os.path.join(home, '.config')
    candidates = [os.path.join(config, 'vlc', 'vlcrc'),
                  os.path.join(home, '.var', 'app', 'org.videolan.VLC', 'config', 'vlc', 'vlcrc'),  # Flatpak
                  os.path.join(home, 'snap', 'vlc', 'current', '.config', 'vlc', 'vlcrc')]  # Snap
    return next((p for p in candidates if os.path.isfile(p)), candidates[0])


VLCRC = _vlcrc()


def vlc_running():
    if sys.platform == 'win32':
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq vlc.exe', '/NH'],
                             capture_output=True, text=True, creationflags=_NO_WINDOW).stdout
        return 'vlc.exe' in out.lower()
    try:
        return subprocess.run(['pgrep', '-x', 'vlc'], capture_output=True).returncode == 0
    except OSError:
        return False


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def pick_port(preferred):
    """preferred boşsa onu, değilse 8765'ten başlayarak ilk boş portu döner."""
    for port in [preferred] + list(range(8765, 8800)):
        if port_free(port):
            return port
    return preferred


def _set(text, key, value_fn, section):
    pat = re.compile(r'^#?' + re.escape(key) + r'=([^\r\n]*)$', re.M)
    m = pat.search(text)
    if not m:
        return text + '\n[%s]\n%s=%s\n' % (section, key, value_fn(None))
    current = None if m.group(0).startswith('#') else m.group(1)
    return text[:m.start()] + '%s=%s' % (key, value_fn(current)) + text[m.end():]


def _add_http(current):
    if not current:
        return 'http'
    return current if 'http' in current.split(':') else current + ':http'


def configure(password, port):
    if not os.path.isfile(VLCRC):
        os.makedirs(os.path.dirname(VLCRC), exist_ok=True)
        text = ''
    else:
        backup = VLCRC + '.vlc-subtitle-translator.bak'
        if not os.path.exists(backup) and not os.path.exists(VLCRC + '.kelimeavcisi.bak'):  # eski ad
            shutil.copy2(VLCRC, backup)
        with open(VLCRC, encoding='utf-8', errors='surrogateescape', newline='') as f:
            text = f.read()
    text = _set(text, 'extraintf', _add_http, 'core')
    text = _set(text, 'http-host', lambda _: '127.0.0.1', 'core')
    text = _set(text, 'http-port', lambda _: str(port), 'core')
    text = _set(text, 'http-password', lambda _: password, 'lua')
    with open(VLCRC, 'w', encoding='utf-8', errors='surrogateescape', newline='') as f:
        f.write(text)
