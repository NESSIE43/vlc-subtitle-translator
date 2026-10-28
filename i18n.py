"""Arayüz dili. Kaynak metinler Türkçedir; _() İngilizce seçiliyse karşılığını döner.

Yeni bir metin eklerken _('...') ile sar ve aşağıdaki EN sözlüğüne İngilizcesini ekle.
"""
import locale
import os
import sys

UI_LANGS = ('tr', 'en')
_lang = 'tr'


def system_lang():
    """Sistem dili Türkçeyse 'tr', değilse 'en'."""
    if sys.platform == 'win32':
        try:
            import ctypes
            if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x1F:  # LANG_TURKISH
                return 'tr'
            return 'en'
        except Exception:
            pass
    for var in ('LC_ALL', 'LC_MESSAGES', 'LANG', 'LANGUAGE'):
        if os.environ.get(var):
            return 'tr' if os.environ[var].lower().startswith('tr') else 'en'
    try:
        loc = locale.getlocale()[0] or ''
    except ValueError:
        loc = ''
    return 'tr' if loc.lower().startswith(('tr', 'turkish')) else 'en'


def init(setting):
    """setting: 'auto', 'tr' ya da 'en'."""
    global _lang
    _lang = setting if setting in UI_LANGS else system_lang()


def current():
    return _lang


def _(text):
    return text if _lang == 'tr' else EN.get(text, text)


EN = {
    # genel
    'VLC Altyazı Çevirmeni': 'VLC Subtitle Translator',
    'VLC için altyazıyla dil öğrenme yardımcısı': 'Learn languages with subtitles in VLC',
    'Ana sayfa': 'Home',
    'Görünüm': 'Appearance',
    'Çeviri': 'Translation',
    'Bağlantı': 'Connection',
    'Arayüz dili': 'Interface language',
    'Otomatik (sistem dili)': 'Automatic (system language)',
    'Arayüz dili değişti. Program şimdi yeniden başlatılsın mı?':
        'The interface language has changed. Restart the program now?',
    'Kaydet': 'Save',

    # durum
    '●  VLC aranıyor': '●  Looking for VLC',
    '●  VLC bulunamadı': '●  VLC not found',
    '●  Bağlı': '●  Connected',
    '●  Şifre yanlış': '●  Wrong password',
    '●  Port dolu': '●  Port in use',
    'Şifre yanlış. "Bağlantı" sekmesinden "VLC\'yi otomatik ayarla"ya bas.':
        'Wrong password. Press "Set up VLC automatically" on the "Connection" tab.',
    'Port %s başka bir program tarafından kullanılıyor. VLC\'yi kapatıp "Bağlantı" sekmesinden '
    '"VLC\'yi otomatik ayarla"ya bas, boş bir port seçilecek.':
        'Port %s is used by another program. Close VLC and press "Set up VLC automatically" on the '
        '"Connection" tab; a free port will be chosen.',
    'VLC açık değil ya da web arayüzü kapalı. İlk kez kullanıyorsan "Bağlantı" sekmesinden '
    '"VLC\'yi otomatik ayarla"ya bas.':
        'VLC is not running or its web interface is off. If this is your first time, press '
        '"Set up VLC automatically" on the "Connection" tab.',

    # ana sayfa
    'Şu an oynatılan': 'Now playing',
    'Altyazı: —': 'Subtitles: —',
    'Altyazı dosyası seç…': 'Choose subtitle file…',
    'Kelimelerin': 'Your words',
    'biliyorum': 'known',
    'öğreniyorum': 'learning',
    'bilmiyorum': 'unknown',
    'favori': 'favorite',
    '★  Kelimelerim / Favoriler': '★  My words / Favorites',
    'Davranış': 'Behavior',
    'Kelimenin üzerine gelince videoyu duraklat': 'Pause the video while hovering a word',
    "VLC'nin kendi altyazısını kapat (çift görünmesin)": "Turn off VLC's own subtitles (avoid showing them twice)",
    'Kelimenin üzerine gel → çevirisi çıkar. Biliyorum / Öğreniyorum / Bilmiyorum ile '
    'renklendir, ☆ ile favorile. Favoriler altı çizili görünür.':
        'Hover a word → see its translation. Color it as Known / Learning / Unknown, '
        'add it to favorites with ☆. Favorites are underlined.',

    # görünüm
    'ÖNİZLEME': 'PREVIEW',
    'Yazı': 'Text',
    'Yazı tipi': 'Font',
    'Boyut': 'Size',
    'Renk': 'Color',
    'Kalın': 'Bold',
    'Siyah kenarlık (açık sahnelerde okunur)': 'Black outline (readable on bright scenes)',
    'Arka plan ve konum': 'Background and position',
    'Opaklık': 'Opacity',
    'Yuvarlak köşeler': 'Rounded corners',
    'Alttan': 'From bottom',
    'Genişlik': 'Width',
    'Varsayılanlara dön': 'Reset to defaults',
    'Renk seç': 'Pick a color',

    # çeviri sekmesi
    'Diller': 'Languages',
    'Altyazı dili: videodaki (öğrendiğin) dil. Çeviri dili: kelimelerin hangi dile çevrileceği.':
        'Subtitle language: the language in the video (the one you are learning). '
        'Translation language: the language words are translated into.',
    'Altyazı dili': 'Subtitle language',
    'Çeviri dili': 'Translation language',
    '⇄  Yer değiştir': '⇄  Swap',
    'Çeviri servisi': 'Translation service',
    'Kendi API anahtarını kullan. Anahtar sadece bu bilgisayarda (data/ayarlar.json) '
    'saklanır ve sadece seçtiğin servise gönderilir.':
        'Use your own API key. The key is stored only on this computer (data/ayarlar.json) '
        'and is sent only to the service you choose.',
    'DeepL API (Free ya da Pro anahtarı)': 'DeepL API (Free or Pro key)',
    'Anahtarsız (resmi değil, sınırlı, her an bozulabilir; sadece denemek için)':
        'No key (unofficial, limited, may break at any time; for trying out only)',
    'API anahtarı': 'API key',
    'Test et': 'Test',
    'Anahtar nasıl alınır? README.tr.md içindeki "Çeviri servisi ve API anahtarı" bölümüne bak.':
        'How do I get a key? See the "Translation service and API key" section in README.md.',
    'Altyazı dili "Otomatik algıla" iken yer değiştirilemez.':
        'Cannot swap while the subtitle language is "Auto-detect".',
    'Anahtar kaydedildi.': 'Key saved.',
    'Deneniyor…': 'Testing…',
    '✓ Çalışıyor: "%s" → "%s"': '✓ Works: "%s" → "%s"',
    'Çeviri alınamadı (internet?)': 'Translation failed (internet?)',
    'Otomatik algıla': 'Auto-detect',

    # bağlantı
    'VLC bağlantısı': 'VLC connection',
    'Program VLC\'ye, VLC\'nin web arayüzü üzerinden (sadece bu bilgisayardan, şifreyle) '
    'bağlanır. İlk kurulumda "VLC\'yi otomatik ayarla" yeterli.':
        "The program talks to VLC through VLC's web interface (only from this computer, with a "
        'password). On first setup, "Set up VLC automatically" is all you need.',
    'Şifre': 'Password',
    "VLC'yi otomatik ayarla": 'Set up VLC automatically',
    'Port bir sayı olmalı.': 'Port must be a number.',
    "Bu programın VLC ile konuşabilmesi için VLC'nin web arayüzünün açılması gerekiyor "
    '(sadece bu bilgisayardan erişilebilir, şifreli).\n\n'
    'VLC ayarlarını şimdi otomatik yapayım mı?':
        "For this program to talk to VLC, VLC's web interface must be turned on "
        '(reachable only from this computer, password protected).\n\n'
        'Set up VLC automatically now?',
    "Ayarları yazabilmem için önce VLC'yi tamamen kapat, sonra 'Yeniden dene'ye bas.":
        "Fully close VLC first so the settings can be written, then press 'Retry'.",
    'VLC ayar dosyası yazılamadı:\n%s': 'Could not write the VLC settings file:\n%s',
    "VLC ayarlandı ✓\n\nŞimdi VLC'yi açıp altyazılı videonu başlat. Bu pencere açık kalsın.":
        'VLC is set up ✓\n\nNow open VLC and start a video with subtitles. Keep this window open.',

    # altyazı
    'Altyazı: video yerel bir dosya değil — "Altyazı dosyası seç" ile seç':
        'Subtitles: the video is not a local file — use "Choose subtitle file"',
    'Altyazı: aranıyor…': 'Subtitles: searching…',
    'Altyazı: videonun içindeki altyazı çıkarılıyor (biraz sürebilir)…':
        'Subtitles: extracting the subtitles embedded in the video (this may take a while)…',
    'Altyazı bulunamadı — "Altyazı dosyası seç" ile .srt dosyasını seç':
        'No subtitles found — use "Choose subtitle file" to pick the .srt file',
    'Altyazı okunamadı: %s': 'Could not read subtitles: %s',
    'Altyazı dosyası boş ya da tanınmadı: ': 'Subtitle file is empty or not recognized: ',
    'Altyazı: %s (%d satır)': 'Subtitles: %s (%d lines)',
    'Altyazı dosyası seç': 'Choose subtitle file',
    'Altyazı': 'Subtitles',
    'Tüm dosyalar': 'All files',
    'gömülü altyazı (%s)': 'embedded subtitles (%s)',

    # çeviri penceresi
    'Biliyorum': 'Known',
    'Öğreniyorum': 'Learning',
    'Bilmiyorum': 'Unknown',
    'çevriliyor…': 'translating…',
    'Çeviri alınamadı: %s': 'Translation failed: %s',
    'Çeviri alınamadı: ': 'Translation failed: ',
    'internet bağlantısı?': 'internet connection?',
    'Cümleyi çevir ›': 'Translate sentence ›',

    # kelimelerim
    'Kelimelerim': 'My words',
    '★  Favoriler': '★  Favorites',
    'Tüm kelimeler': 'All words',
    '●  Biliyorum': '●  Known',
    '●  Öğreniyorum': '●  Learning',
    '●  Bilmiyorum': '●  Unknown',
    'Kelime': 'Word',
    'Durum': 'Status',
    'Örnek cümle': 'Example sentence',
    'Eklenme': 'Added',
    'Favori': 'Favorite',
    'Ara': 'Search',
    'Renksiz': 'No color',
    '★ Favori': '★ Favorite',
    'Çeviriyi düzenle': 'Edit translation',
    'Sil': 'Delete',
    'CSV olarak dışa aktar': 'Export as CSV',
    '%d gösteriliyor · toplam %d kelime': '%d shown · %d words in total',
    'Önce listeden kelime seç.': 'Select a word from the list first.',
    '"%s" için çeviri:': 'Translation for "%s":',
    '%d kelime silinsin mi?': 'Delete %d word(s)?',
    'kelimelerim.csv': 'my_words.csv',
    'evet': 'yes',
    'Kaydedildi:\n': 'Saved:\n',

    # çeviri servisleri
    '%s anahtarı geçersiz ya da yetkisiz': '%s key is invalid or not authorized',
    '%s kotası doldu / çok fazla istek': '%s quota exceeded / too many requests',
    '%s bu dil çiftini desteklemiyor olabilir': '%s may not support this language pair',
    '%s hata verdi (HTTP %d)': '%s returned an error (HTTP %d)',
    'internet bağlantısı yok ya da ücretsiz servis engelledi':
        'no internet connection, or the free service blocked the request',
    "DeepL'e bağlanılamadı (internet?)": 'Could not connect to DeepL (internet?)',
    'DeepL boş çeviri döndü': 'DeepL returned an empty translation',
    "Google Cloud'a bağlanılamadı (internet?)": 'Could not connect to Google Cloud (internet?)',
    'Google Cloud boş çeviri döndü': 'Google Cloud returned an empty translation',
    'altyazı dili ile çeviri dili aynı': 'the subtitle and translation languages are the same',
    'API anahtarı girilmemiş ("Çeviri" sekmesi)': 'no API key entered ("Translation" tab)',
}
