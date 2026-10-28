"""Desteklenen diller ve altyazı dosyası/akışı eşleştirmesi için kodları."""
import i18n
from i18n import _

# (Google kodu, görünen ad, ISO 639-2 kodları, İngilizce ad)
LANGS = [
    ('en', 'İngilizce', 'eng', 'english'),
    ('tr', 'Türkçe', 'tur', 'turkish'),
    ('de', 'Almanca', 'ger deu', 'german'),
    ('fr', 'Fransızca', 'fre fra', 'french'),
    ('es', 'İspanyolca', 'spa', 'spanish'),
    ('it', 'İtalyanca', 'ita', 'italian'),
    ('pt', 'Portekizce', 'por', 'portuguese'),
    ('ru', 'Rusça', 'rus', 'russian'),
    ('ja', 'Japonca', 'jpn', 'japanese'),
    ('ko', 'Korece', 'kor', 'korean'),
    ('zh-CN', 'Çince (Basitleştirilmiş)', 'chi zho chs', 'chinese'),
    ('zh-TW', 'Çince (Geleneksel)', 'chi zho cht', 'chinese'),
    ('ar', 'Arapça', 'ara', 'arabic'),
    ('fa', 'Farsça', 'per fas', 'persian'),
    ('he', 'İbranice', 'heb', 'hebrew'),
    ('hi', 'Hintçe', 'hin', 'hindi'),
    ('nl', 'Felemenkçe', 'dut nld', 'dutch'),
    ('pl', 'Lehçe', 'pol', 'polish'),
    ('uk', 'Ukraynaca', 'ukr', 'ukrainian'),
    ('sv', 'İsveççe', 'swe', 'swedish'),
    ('nb', 'Norveççe', 'nor nob', 'norwegian'),
    ('da', 'Danca', 'dan', 'danish'),
    ('fi', 'Fince', 'fin', 'finnish'),
    ('el', 'Yunanca', 'gre ell', 'greek'),
    ('cs', 'Çekçe', 'cze ces', 'czech'),
    ('sk', 'Slovakça', 'slo slk', 'slovak'),
    ('hu', 'Macarca', 'hun', 'hungarian'),
    ('ro', 'Rumence', 'rum ron', 'romanian'),
    ('bg', 'Bulgarca', 'bul', 'bulgarian'),
    ('sr', 'Sırpça', 'srp', 'serbian'),
    ('hr', 'Hırvatça', 'hrv', 'croatian'),
    ('bs', 'Boşnakça', 'bos', 'bosnian'),
    ('sl', 'Slovence', 'slv', 'slovenian'),
    ('sq', 'Arnavutça', 'alb sqi', 'albanian'),
    ('lt', 'Litvanca', 'lit', 'lithuanian'),
    ('lv', 'Letonca', 'lav', 'latvian'),
    ('et', 'Estonca', 'est', 'estonian'),
    ('az', 'Azerbaycan Türkçesi', 'aze', 'azerbaijani'),
    ('kk', 'Kazakça', 'kaz', 'kazakh'),
    ('uz', 'Özbekçe', 'uzb', 'uzbek'),
    ('ka', 'Gürcüce', 'geo kat', 'georgian'),
    ('ku', 'Kürtçe (Kurmanci)', 'kur kmr', 'kurdish'),
    ('id', 'Endonezce', 'ind', 'indonesian'),
    ('ms', 'Malayca', 'may msa', 'malay'),
    ('th', 'Tayca', 'tha', 'thai'),
    ('vi', 'Vietnamca', 'vie', 'vietnamese'),
]

AUTO = 'auto'
NAMES = {code: name for code, name, iso3, english in LANGS}
# İngilizce arayüzde gösterilecek adlar (çoğu İngilizce adın büyük harflisi)
EN_NAMES = {code: english.capitalize() for code, name, iso3, english in LANGS}
EN_NAMES.update({'zh-CN': 'Chinese (Simplified)', 'zh-TW': 'Chinese (Traditional)',
                 'ku': 'Kurdish (Kurmanji)'})


def name(code):
    if code == AUTO:
        return _('Otomatik algıla')
    return (NAMES if i18n.current() == 'tr' else EN_NAMES).get(code, code)


def tokens(code):
    """Bir dili dosya adında / ffprobe etiketinde tanımak için kullanılan kelimeler."""
    for c, tr_name, iso3, english in LANGS:
        if c == code:
            base = c.split('-')[0].lower()
            return {c.lower(), base, english} | set(iso3.split()) | {tr_name.lower()}
    return set()


def label(code):
    return name(code) if code == AUTO else '%s (%s)' % (name(code), code)


_ALPHABET = 'abcçdefgğhıijklmnoöpqrsştuüvwxyz'


def _sort_key(text):
    if i18n.current() != 'tr':
        return text.lower()
    text = text.replace('İ', 'i').replace('I', 'ı').lower()
    return [_ALPHABET.find(ch) if ch in _ALPHABET else 100 + ord(ch) for ch in text]


def choices(with_auto=False):
    """Açılır liste için [(kod, etiket)], arayüz dilinin alfabesine göre sıralı."""
    codes = sorted((lang[0] for lang in LANGS), key=lambda c: _sort_key(name(c)))
    return [(c, label(c)) for c in ([AUTO] if with_auto else []) + codes]
