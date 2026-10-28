"""Çeviri servisleri.

- 'deepl'  : DeepL API (kullanıcının kendi anahtarı; Free ve Pro anahtarları desteklenir)
- 'google' : Google Cloud Translation API v2 (kullanıcının kendi anahtarı)
- 'free'   : anahtarsız Google Translate ucu, olmazsa MyMemory. Resmi değildir,
             her an çalışmayı bırakabilir; sadece denemek için.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from i18n import _

_HEADERS = {'User-Agent': 'Mozilla/5.0'}

PROVIDERS = ('free', 'deepl', 'google')


class TranslateError(Exception):
    """Kullanıcıya gösterilebilecek kısa bir açıklama taşır."""


def _fetch_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=dict(_HEADERS, **(headers or {})))
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read().decode('utf-8'))


def _http_error(e, service):
    try:
        body = e.read().decode('utf-8', 'replace').lower()
    except Exception:
        body = ''
    if e.code in (401, 403) or 'api key' in body or 'api_key' in body:
        return TranslateError(_('%s anahtarı geçersiz ya da yetkisiz') % service)
    if e.code in (429, 456):
        return TranslateError(_('%s kotası doldu / çok fazla istek') % service)
    if e.code == 400:
        return TranslateError(_('%s bu dil çiftini desteklemiyor olabilir') % service)
    return TranslateError(_('%s hata verdi (HTTP %d)') % (service, e.code))


# -- anahtarsız ---------------------------------------------------------
def _google_free(text, sl, tl, with_dict):
    params = [('client', 'gtx'), ('sl', sl), ('tl', tl), ('hl', tl), ('dt', 't')]
    if with_dict:
        params.append(('dt', 'bd'))  # kelime türleri (hl dilinde gelir) ve diğer anlamlar
    params.append(('q', text))
    data = _fetch_json('https://translate.googleapis.com/translate_a/single?'
                       + urllib.parse.urlencode(params))
    main = ''.join(seg[0] for seg in (data[0] or []) if seg and seg[0]).strip()
    alts = []
    if with_dict and len(data) > 1 and isinstance(data[1], list):
        for entry in data[1]:
            if isinstance(entry, list) and len(entry) > 1 and entry[1]:
                alts.append([entry[0], entry[1][:5]])
    if not main:
        raise ValueError('boş çeviri')
    return {'main': main, 'alts': alts}


def _mymemory(text, sl, tl):
    pair = '%s|%s' % ('autodetect' if sl == 'auto' else sl, tl)
    data = _fetch_json('https://api.mymemory.translated.net/get?'
                       + urllib.parse.urlencode({'q': text, 'langpair': pair}))
    main = (data.get('responseData') or {}).get('translatedText', '').strip()
    if not main:
        raise ValueError('boş çeviri')
    return {'main': main, 'alts': []}


def _free(text, sl, tl, with_dict):
    try:
        return _google_free(text, sl, tl, with_dict)
    except Exception:
        try:
            return _mymemory(text, sl, tl)
        except Exception as e:
            raise TranslateError(_('internet bağlantısı yok ya da ücretsiz servis engelledi')) from e


# -- kendi anahtarınla --------------------------------------------------
# DeepL bazı hedef dillerde bölge ister; kaynak dilde ise sadece ana kodu kabul eder.
_DEEPL_TARGET = {'en': 'EN-US', 'pt': 'PT-BR', 'zh-CN': 'ZH-HANS', 'zh-TW': 'ZH-HANT'}


def _deepl(text, sl, tl, key):
    host = 'api-free.deepl.com' if key.endswith(':fx') else 'api.deepl.com'
    body = {'text': [text], 'target_lang': _DEEPL_TARGET.get(tl, tl.upper())}
    if sl != 'auto':
        body['source_lang'] = sl.split('-')[0].upper()
    try:
        data = _fetch_json('https://%s/v2/translate' % host, json.dumps(body).encode('utf-8'),
                           {'Authorization': 'DeepL-Auth-Key ' + key,
                            'Content-Type': 'application/json'})
    except urllib.error.HTTPError as e:
        raise _http_error(e, 'DeepL') from e
    except urllib.error.URLError as e:
        raise TranslateError(_('DeepL\'e bağlanılamadı (internet?)')) from e
    main = ((data.get('translations') or [{}])[0].get('text') or '').strip()
    if not main:
        raise TranslateError(_('DeepL boş çeviri döndü'))
    return {'main': main, 'alts': []}


def _google_cloud(text, sl, tl, key):
    form = {'q': text, 'target': tl, 'format': 'text'}
    if sl != 'auto':
        form['source'] = sl
    try:
        data = _fetch_json('https://translation.googleapis.com/language/translate/v2?'
                           + urllib.parse.urlencode({'key': key}),
                           urllib.parse.urlencode(form).encode('utf-8'),
                           {'Content-Type': 'application/x-www-form-urlencoded'})
    except urllib.error.HTTPError as e:
        raise _http_error(e, 'Google Cloud') from e
    except urllib.error.URLError as e:
        raise TranslateError(_('Google Cloud\'a bağlanılamadı (internet?)')) from e
    tr = ((data.get('data') or {}).get('translations') or [{}])[0]
    main = (tr.get('translatedText') or '').strip()
    if not main:
        raise TranslateError(_('Google Cloud boş çeviri döndü'))
    return {'main': main, 'alts': []}


def _translate(text, sl, tl, provider, key, with_dict):
    if sl == tl:
        raise TranslateError(_('altyazı dili ile çeviri dili aynı'))
    if provider in ('deepl', 'google'):
        if not key:
            raise TranslateError(_('API anahtarı girilmemiş ("Çeviri" sekmesi)'))
        return (_deepl if provider == 'deepl' else _google_cloud)(text, sl, tl, key)
    return _free(text, sl, tl, with_dict)


def translate_word(word, sl, tl, provider='free', key=''):
    return _translate(word, sl, tl, provider, key, True)


def translate_sentence(text, sl, tl, provider='free', key=''):
    return _translate(' '.join(text.split()), sl, tl, provider, key, False)['main']
