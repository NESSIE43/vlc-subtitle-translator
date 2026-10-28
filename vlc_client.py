"""VLC'nin web (HTTP) arayüzü ile konuşan küçük istemci."""
import base64
import json
import urllib.error
import urllib.parse
import urllib.request


class VLCAuthError(Exception):
    pass


# localhost için sistem proxy ayarlarını yok say
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class VLCClient:
    def __init__(self, port, password, host='127.0.0.1'):
        self.base = 'http://%s:%s/requests/' % (host, port)
        token = base64.b64encode((':' + password).encode('utf-8')).decode('ascii')
        self.headers = {'Authorization': 'Basic ' + token}

    def _get(self, name, params=None, timeout=1.5):
        url = self.base + name
        if params:
            url += '?' + urllib.parse.urlencode(params)
        try:
            with _opener.open(urllib.request.Request(url, headers=self.headers),
                              timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise VLCAuthError() from e
            raise

    def status(self):
        return self._get('status.json')

    def command(self, command, **params):
        return self._get('status.json', dict(command=command, **params))

    def current_uri(self):
        stack = [self._get('playlist.json')]
        while stack:
            node = stack.pop()
            if node.get('current') == 'current' and node.get('uri'):
                return node['uri']
            stack.extend(node.get('children') or [])
        return None


def uri_to_path(uri):
    """file:///C:/x%20y.mkv -> C:\\x y.mkv  (yerel dosya değilse None)."""
    if not uri or not uri.startswith('file:'):
        return None
    p = urllib.parse.urlparse(uri)
    path = urllib.request.url2pathname(p.path)
    if p.netloc:
        path = '\\\\' + p.netloc + path
    return path
