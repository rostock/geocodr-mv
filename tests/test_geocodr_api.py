import json
import pytest
import requests
import threading
import time


class Result(object):
  def __init__(self, resp):
    self.resp = resp
    self.doc = resp.json()
    assert self.doc.get('type') == 'FeatureCollection', 'Result is not type=FeatureCollection'

  @property
  def features(self):
    return self.doc['features']


class Error(object):
  def __init__(self, resp):
    self.resp = resp
    self.doc = resp.json()
    self.status = self.doc['status']
    self.message = self.doc['message']


class Client(object):
  def __init__(self, url, key=None):
    self.url = url
    self.key = key
    self._s = requests.Session()

  @staticmethod
  def handle_resp(resp):
    if resp.ok:
      return Result(resp)
    return Error(resp)

  def search(self, q, **kw):
    if 'type' not in kw:
      kw['type'] = 'search'
    return self.call(q, **kw)

  def reverse(self, q, **kw):
    if 'type' not in kw:
      kw['type'] = 'reverse'
    return self.call(q, **kw)

  def call(self, q, **params):
    d = {'query': q}
    if self.key:
      d['key'] = self.key
    d.update(params)

    resp = self._s.get(self.url, params=d)
    return self.handle_resp(resp)


class JSONClient(object):
  def __init__(self, url, key=None):
    self.url = url
    self.key = key
    self._s = requests.Session()

  @staticmethod
  def handle_resp(resp):
    if resp.ok:
      return Result(resp)
    return Error(resp)

  def search(self, q, **kw):
    if 'type' not in kw:
      kw['type'] = 'search'
    return self.call(q, **kw)

  def reverse(self, q, **kw):
    if 'type' not in kw:
      kw['type'] = 'reverse'
    return self.call(q, **kw)

  def call(self, q, **kw):
    d = {}
    params = {}
    d['query'] = q
    d.update(kw)
    if self.key:
      params['key'] = self.key
    if 'key' in kw:
      params['key'] = kw.pop('key')

    resp = self._s.post(self.url, json=d, params=params)
    return self.handle_resp(resp)


@pytest.fixture(
  params=[
    'get',
    'json',
  ],
  scope='session',
)
def client(geocodr_url, solr_url, geocodr_test_key, geocodr_mapping, request):
  if solr_url != "":
    from geocodr.api import create_app
    app = create_app({
      'solr_url': solr_url,
      'mapping': geocodr_mapping,
    })
    server = ServerThread(app)
    server.start()

    # Wait randomish time to allows SocketServer to initialize itself.
    # Replace this with proper event telling the server is up.
    time.sleep(0.1)

    # assert server.srv is not None, "Could not start the test web server"

    host_base = HOST_BASE

    geocodr_url = host_base

  if request.param == 'get':
    return Client(geocodr_url + '/query', key=geocodr_test_key)
  elif request.param == 'json':
    return JSONClient(geocodr_url + '/query', key=geocodr_test_key)


@pytest.mark.parametrize('q,params,error', [
  ('Rostock', {}, "Parameter 'class' is required"),
  ('Rostock', {'class': 'unknown'}, "Invalid class 'unknown'"),
  ('Rostock', {'class': 'address', 'type': 'unknown'}, 'Invalid request type.'),
])
def test_invalid_requests(client, q, params, error):
  res = client.search(q, **params)
  assert res.status == 400
  assert error in res.message


def test_not_found(client):
  res = client.search('dflskjdhf lskjdhf lskjdhf lskjdfh lskjdh',
                      **{'class': 'address'})
  assert len(res.features) == 0


def test_search_limit(client):
  res = client.search('Rostock', **{'class': 'address'})
  assert len(res.features) == 100

  res = client.search('Rostock', limit=10, **{'class': 'address'})
  assert len(res.features) == 10

  # return at least one result
  res = client.search('Rostock', limit=-10, **{'class': 'address'})
  assert len(res.features) == 1


def test_reverse_invalid_epsg(client):
  res = client.reverse('Rostock', in_epsg=99999, **{'class': 'adress'})
  assert res.status == 400
  assert 'Invalid parameter value: unknown 99999' in res.message


def test_search_reverse_error(client):
  res = client.reverse('12.1441154.192757', in_epsg=4326, **{'class': 'address'})
  assert res.status == 400
  assert 'Invalid parameter value' in res.message


def test_headers(client):
  res = client.search('rostock steinstr 1',
                      **{'class': 'address'})
  assert res.resp.headers['content-type'] == 'application/json; charset=utf-8'
  assert res.resp.headers['access-control-allow-origin'] == '*'
  assert len(res.features) > 0


def test_jsonp(client):
  if isinstance(client, JSONClient):
    resp = requests.post(client.url, params={
      'callback': 'test_callback',
      'key': client.key,
    }, json={
      'query': 'rostock steinstr 1',
      'class': 'address',
      'type': 'search',
    })
  else:
    resp = requests.get(client.url, params={
      'query': 'rostock steinstr 1',
      'callback': 'test_callback',
      'class': 'address',
      'type': 'search',
      'key': client.key,
    })
  assert resp.headers['content-type'] == 'application/javascript'
  assert resp.headers['access-control-allow-origin'] == '*'
  assert resp.content.startswith(b'test_callback({\n')
  assert resp.content.endswith(b'\n});')
  data = resp.content[len('test_callback('):-2]
  if isinstance(resp.content, bytes):
    data = data.decode('utf-8')
  fc = json.loads(data)
  assert fc['type'] == 'FeatureCollection'


@pytest.mark.parametrize("query", [
  '  rostock ',
  ' RøsTOCK',  # find fuzzy results
  ' "Rostock"',
  " 'Rostock'",
  r'-{}[]\Rostock" +Hauptstr',
])
def test_invalid_chars(client, query):
  """
  Check that special chars are replaced with whitespace.
  """
  res = client.search(query,
                      **{'class': 'address'})
  assert len(res.features) > 0


@pytest.mark.parametrize("radius,min_features,max_features", [
  (None, 10, 20),  # default 50
  (5, 1, 3),
  (10, 3, 5),
  (50, 10, 20),
  (500, 80, 80),  # limit
])
def test_reverse_radius(client, radius, min_features, max_features):
  kw = {'class': 'address'}
  if radius:
    kw['radius'] = radius
  res = client.reverse(
    '12.144111609107474,54.19275740009377',
    limit=80,
    in_epsg=4326, **kw)
  assert min_features <= len(res.features) <= max_features
  # first result should be direct hit
  assert res.features[0]['properties']['entfernung'] < 0.1
  last_dist = 0
  if not radius:
    radius = 50  # default
  # other results should be ordered by distance
  for f in res.features:
    dist = f['properties']['entfernung']
    assert dist < radius
    assert dist >= last_dist
    last_dist = dist


@pytest.mark.parametrize("radius,min_features,max_features", [
  (5, 1, 3),
  (10, 3, 5),
  (50, 10, 20),
  (500, 80, 80),  # limit
])
def test_reverse_peri_radius(client, radius, min_features, max_features):
  res = client.reverse(
    'ignored for reverse with peri_coord',
    peri_coord='12.144111609107474,54.19275740009377', peri_epsg=4326,
    peri_radius=radius,
    radius=1000,  # ignored
    limit=80,
    in_epsg=4326, **{'class': 'address'})
  assert min_features <= len(res.features) <= max_features
  # first result should be direct hit
  assert res.features[0]['properties']['entfernung'] < 0.1
  last_dist = 0
  # other results should be ordered by distance
  for f in res.features:
    dist = f['properties']['entfernung']
    assert dist < radius
    assert dist >= last_dist
    last_dist = dist


def test_search_neubukow(client):
  """
  F.1.1 Suchklasse Adresse, Suche nach neubukow
  """
  res = client.search('neubukow', limit=500, **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Gemeinde', 'gemeinde_name': 'Neubukow, Stadt'}),
    R({'objektgruppe': 'Gemeindeteil', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Neubukow'}),
    R({'objektgruppe': 'Gemeindeteil', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Panzow'}),
  ]

  assert_results(res, expected)

  """
  F.1.2 Suchklasse Adresse, Suche nach parkeNt Wiesen
  """
  res = client.search('parkeNt Wiesen', limit=100, **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Straße', 'strasse_name': 'Wiesengrund',
       'gemeinde_name': 'Bartenshagen-Parkentin', 'gemeindeteil_name': 'Parkentin'}),
    R({'objektgruppe': 'Straße', 'strasse_name': 'Wiesenstr.',
       'gemeinde_name': 'Bartenshagen-Parkentin', 'gemeindeteil_name': 'Neuhof'}),
    R({'objektgruppe': 'Straße', 'strasse_name': 'An der Streuobstwiese',
       'gemeinde_name': 'Bartenshagen-Parkentin', 'gemeindeteil_name': 'Bartenshagen'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Wiesengrund', 'hausnummer': '1',
       'gemeinde_name': 'Bartenshagen-Parkentin', 'gemeindeteil_name': 'Parkentin'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Wiesengrund', 'hausnummer': '2',
       'gemeinde_name': 'Bartenshagen-Parkentin', 'gemeindeteil_name': 'Parkentin'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Wiesengrund', 'hausnummer': '3',
       'gemeinde_name': 'Bartenshagen-Parkentin', 'gemeindeteil_name': 'Parkentin'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Wiesenstr.', 'hausnummer': '1',
       'gemeinde_name': 'Bartenshagen-Parkentin', 'gemeindeteil_name': 'Neuhof'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Wiesenstr.', 'hausnummer': '1',
       'hausnummer_zusatz': 'a', 'gemeinde_name': 'Bartenshagen-Parkentin',
       'gemeindeteil_name': 'Neuhof'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Wiesenstr.', 'hausnummer': '2',
       'gemeinde_name': 'Bartenshagen-Parkentin', 'gemeindeteil_name': 'Neuhof'}),
  ]

  assert_results(res, expected)


@pytest.mark.parametrize("query", [
  'seeStr.,Rosto',
  'Rostock seestrasse',
])
def test_search_seestr(client, query):
  """
  F.1.3 Suchklasse Adresse, Suche nach seeStr.,Rosto
  """
  res = client.search(query, limit=100, **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Straße', 'strasse_name': 'Seestr.',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Seebad Warnemünde'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Seestr.', 'hausnummer': '1',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Seebad Warnemünde'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Seestr.', 'hausnummer': '2',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Seebad Warnemünde'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Seestr.', 'hausnummer': '3',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Seebad Warnemünde'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Seestr.', 'hausnummer': '4',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Seebad Warnemünde'}),
  ]

  assert_results(res, expected)


def test_search_sportplatz(client):
  """
  F.1.4 Suchklasse Adresse, Suche nach sporrtplats kro¨hpelin 6
  """
  res = client.search('sporrtplats kröhpelin 6', **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Am Sportplatz', 'hausnummer': '6',
       'gemeinde_name': 'Kröpelin, Stadt', 'gemeindeteil_name': 'Schmadebeck'}),
  ]

  assert_results(res, expected)


def test_search_neubukow_limit(client):
  """
  F.1.5 SuchklasseAdresse,Suchenachneubukow,Beschra¨nkungTrefferlistenla¨nge
  """
  res = client.search('neubukow', limit=8, **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Gemeinde', 'gemeinde_name': 'Neubukow, Stadt'}),
    R({'objektgruppe': 'Gemeindeteil', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Neubukow'}),
    R({'objektgruppe': 'Gemeindeteil', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Panzow'}),
    R({'objektgruppe': 'Gemeindeteil', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Buschmühlen'}),
  ]

  assert_results(res, expected)


def test_search_neubukow_bbox(client):
  """
  F.1.6 Suchklasse Adresse, Suche nach neubukow, „Bounding-box“-Filterung
  """
  res = client.search('neubukow', bbox='11.67596,54.03998,11.67763,54.04059', bbox_epsg=4326,
                      limit=500, **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Gemeinde', 'gemeinde_name': 'Neubukow, Stadt'}),
    R({'objektgruppe': 'Gemeindeteil', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Malpendorf'}),
    R({'objektgruppe': 'Straße', 'strasse_name': 'Dorfstr.', 'gemeinde_name': 'Malpendorf',
       'gemeinde_name': 'Neubukow, Stadt'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Dorfstr.', 'hausnummer': '13',
       'gemeinde_name': 'Malpendorf', 'gemeinde_name': 'Neubukow, Stadt'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Dorfstr.', 'hausnummer': '13',
       'hausnummer_zusatz': 'a', 'gemeinde_name': 'Malpendorf',
       'gemeinde_name': 'Neubukow, Stadt'}),
  ]

  assert_results(res, expected)


def test_search_neubukow_peri(client):
  """
  F.1.7 Suchklasse Adresse, Suche nach neubukow, Umkreis-Filterung
  """
  res = client.search('neubukow', peri_coord='280081.485,5992752.284', peri_radius='115.3',
                      peri_epsg=25833, limit=500, **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Gemeinde', 'gemeinde_name': 'Neubukow, Stadt'}),
    R({'objektgruppe': 'Gemeindeteil', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Buschmühlen'}),
    R({'objektgruppe': 'Straße', 'strasse_name': 'Hauptstr.', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Buschmühlen'}),
    R({'objektgruppe': 'Straße', 'strasse_name': 'Grüner Weg',
       'gemeinde_name': 'Neubukow, Stadt'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Grüner Weg', 'hausnummer': '1',
       'gemeinde_name': 'Neubukow, Stadt', 'gemeindeteil_name': 'Buschmühlen'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Grüner Weg', 'hausnummer': '2',
       'gemeinde_name': 'Neubukow, Stadt', 'gemeindeteil_name': 'Buschmühlen'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Grüner Weg', 'hausnummer': '3',
       'gemeinde_name': 'Neubukow, Stadt', 'gemeindeteil_name': 'Buschmühlen'}),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Grüner Weg', 'hausnummer': '4',
       'gemeinde_name': 'Neubukow, Stadt', 'gemeindeteil_name': 'Buschmühlen'}),
  ]

  assert_results(res, expected)


@pytest.mark.parametrize("query", [
  'parkentin, flur 1',
  'parkentin 1',
  '1320901',
  '132090-1',
  '2090 flur 1',
])
def test_search_parcel_flur_1(client, query):
  """
  F.1.8 Suchklasse Flurstück, Suche nach parkentin, flur 1
  """
  res = client.search(query, **{'class': 'parcel'})

  expected = [
    R({'objektgruppe': 'Flur', 'flur': '001', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'gemeinde_name': 'Bartenshagen-Parkentin'}),
    R({'objektgruppe': 'Flurstück', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'flurstueckskennzeichen': '132090-001-00001'}),
  ]

  assert_results(res, expected)


@pytest.mark.parametrize("query", [
  'flurbezirk ii',
  '132241',
  '2241',
])
def test_search_parcel_flurbezirk(client, query):
  """
  F.1.10 Suchklasse Flurstück, Suche nach flurbezirk ii
  """
  res = client.search(query, **{'class': 'parcel'})

  expected = [
    R({'objektgruppe': 'Gemarkung', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '001', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '002', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '003', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '004', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '005', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '006', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '007', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '008', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '009', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flur', 'flur': '010', 'gemarkung_name': 'Flurbezirk II',
       'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flurstück', 'flurstueckskennzeichen': '132241-001-00004/0008',
       'gemarkung_name': 'Flurbezirk II', 'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Flurstück', 'flurstueckskennzeichen': '132241-001-00004/0009',
       'gemarkung_name': 'Flurbezirk II', 'gemarkung_schluessel': '132241',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
  ]

  assert_results(res, expected)


@pytest.mark.parametrize("query,expected,n", [
  ('132232 1,7', None, 0),  # F.1.9
  ('132232 1,157', '132232-001-00157/0002', 2),  # F.1.9
  ('132232 1,157/4', '132232-001-00157/0004', 1),
  ('132232 1,157 4', '132232-001-00157/0004', 1),
  ('132232 flur1 157', '132232-001-00157/0002', 2),
  ('2232 1,7', None, 0),  # F.1.9
  ('2232 1,157', '132232-001-00157/0002', 2),  # F.1.9
  ('2232 1,157/4', '132232-001-00157/0004', 1),
  ('2232 1,157 4', '132232-001-00157/0004', 1),
  ('2232 flur1 157', '132232-001-00157/0002', 2),
  ('Krummendorf flur1 157', '132232-001-00157/0002', 7),
  ('krumendorf flur1 157', '132232-001-00157/0002', 7),
  ('Krummendorf 1 157', '132232-001-00157/0002', 7),
  ('Krummendorf 1 157/2', '132232-001-00157/0002', 2),
  ('132232-001-00157', '132232-001-00157/0002', 2),  # F.1.11
  ('132232-001-00157-02', '132232-001-00157/0002', 1),
  ('132232001001570004', '132232-001-00157/0004', 1),  # F.1.12
  ('2232-001-00157', '132232-001-00157/0002', 2),  # F.1.11
  ('2232-001-00157-02', '132232-001-00157/0002', 1),
  ('2232001001570004', '132232-001-00157/0004', 1),  # F.1.12
])
def test_search_parcel_long(client, query, expected, n):
  """
  F.1.9 Suchklasse Flurstück, Suche nach 13223 21, 7
  F.1.11 Suchklasse Flurstück, Suche nach 132232-001-00157
  F.1.12 Suchklasse Flurstück, Suche nach 132232001001570004
  """
  res = client.search(query, **{'class': 'parcel'})
  assert len(res.features) == n
  if n > 0:
    assert res.features[0]['properties']['flurstueckskennzeichen'] == expected


@pytest.mark.parametrize("query,expected,at_least", [
  ('157', '132232-001-00157/0002', 3000),
  ('157/2', '132232-001-00157/0002', 250),
  ('2232 157/2', '132232-001-00157/0002', 1),
  ('krummendorf 157/2', '132232-001-00157/0002', 1),
])
def test_search_parcel_short(client, query, expected, at_least):
  """
  """
  res = client.search(query, **{'limit': max(at_least, 100), 'class': 'parcel'})
  assert len(res.features) >= at_least
  for f in res.features:
    if f['properties']['flurstueckskennzeichen'] == expected:
      return
  else:
    assert False, '%s not found in %d results' % (expected, len(res.features))


def test_search_school(client):
  """
  F.1.13 Suchklasse Schule, Suche nach jenapla
  """
  res = client.search('jenapla', **{'class': 'school'})

  expected = [
    R({'objektgruppe': 'Schule', 'bezeichnung': 'Jenaplanschule Rostock', 'art': 'Primarbereich',
       'strasse_name': 'Lindenstr.', 'hausnummer': '3a',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Schule',
       'bezeichnung': 'Jenaplanschule Rostock - Integrierte Gesamtschule',
       'art': 'Sekundarbereich I', 'strasse_name': 'Blücherstr.', 'hausnummer': '42',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Schule',
       'bezeichnung': 'Jenaplanschule Rostock - Integrierte Gesamtschule',
       'art': 'Sekundarbereich I', 'strasse_name': 'Lindenstr.', 'hausnummer': '3a',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
  ]

  assert_results(res, expected)


def test_search_school_address(client):
  """
  F.1.14 Suchklasse Adresse und Suchklasse Schule, Suche nach rostock,barnstorfer weg 21a
  """
  res = client.search('rostock,barnstorfer weg 21a', **{'class': 'school,address'})

  expected = [
    R({'objektgruppe': 'Adresse', 'gemeindeteil_name': 'Kröpeliner-Tor-Vorstadt',
       'strasse_name': 'Barnstorfer Weg', 'hausnummer': '21', 'hausnummer_zusatz': 'a',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
    R({'objektgruppe': 'Schule', 'bezeichnung': 'Grundschule am Margaretenplatz',
       'art': 'Primarbereich', 'strasse_name': 'Barnstorfer Weg', 'hausnummer': '21a',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}),
  ]

  assert_results(res, expected)


def test_reverse_address(client):
  """
  F.2.1 Suchklasse Adresse, Suche nach 307663,6004522.21
  """
  res = client.search('307663,6004522.21', in_epsg=25833, type='reverse', **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Gemeinde', 'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'},
      distance=0),
    R({'objektgruppe': 'Gemeindeteil', 'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Lichtenhagen'}, distance=0),
    R({'objektgruppe': 'Straße', 'strasse_name': 'Stettiner Str.',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}, distance=1),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Stettiner Str.', 'hausnummer': '26',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Lichtenhagen'}, distance=15),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Stettiner Str.', 'hausnummer': '35',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Lichtenhagen'}, distance=20),
  ]

  assert_results(res, expected)


def test_reverse_parcel(client):
  """
  F.2.2 Suchklasse Flurstück, Suche nach 307663,6004522.21
  """
  res = client.search('307663,6004522.21', in_epsg=25833, type='reverse', **{'class': 'parcel'})

  expected = [
    R({'objektgruppe': 'Gemarkung', 'gemarkung_name': 'Lütten Klein',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}, distance=0),
    R({'objektgruppe': 'Flur', 'flur': '003', 'gemarkung_name': 'Lütten Klein',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}, distance=0),
    R({'objektgruppe': 'Flurstück', 'flurstueckskennzeichen': '132221-003-00022/0101',
       'gemarkung_name': 'Lütten Klein',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}, distance=0),
    R({'objektgruppe': 'Flurstück', 'flurstueckskennzeichen': '132221-003-00022/0096',
       'gemarkung_name': 'Lütten Klein',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}, distance=4),
    R({'objektgruppe': 'Flurstück', 'flurstueckskennzeichen': '132221-003-00022/0110',
       'gemarkung_name': 'Lütten Klein',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}, distance=4),
    R({'objektgruppe': 'Flurstück', 'flurstueckskennzeichen': '132221-003-00022/0116',
       'gemarkung_name': 'Lütten Klein',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt'}, distance=6),
  ]

  assert_results(res, expected)


def test_reverse_bbox(client):
  """
  F.2.3 Suchklasse Adresse, „Bounding-box“-Filterung
  """
  res = client.search('12345,67890', in_epsg=9999, bbox='11.67596,54.03998,11.67763,54.04059',
                      bbox_epsg=4326, type='reverse', **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Gemeinde', 'gemeinde_name': 'Neubukow, Stadt'}, distance=0),
    R({'objektgruppe': 'Gemeindeteil', 'gemeindeteil_name': 'Malpendorf',
       'gemeinde_name': 'Neubukow, Stadt'}, distance=0),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Dorfstr.', 'hausnummer': '13',
       'hausnummer_zusatz': None, 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Malpendorf'}, distance=20),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Dorfstr.', 'hausnummer': '13',
       'hausnummer_zusatz': 'a', 'gemeinde_name': 'Neubukow, Stadt',
       'gemeindeteil_name': 'Malpendorf'}, distance=35),
  ]

  assert_results(res, expected)


def test_reverse_peri(client):
  """
  F.2.4 Suchklasse Adresse, Umkreis-Filterung
  """
  res = client.search('12345,67890', in_epsg=9999, peri_coord='280081.485,5992752.284',
                      peri_radius='115.3', peri_epsg=25833, type='reverse', **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Gemeinde', 'gemeinde_name': 'Neubukow, Stadt'}, distance=0),
    R({'objektgruppe': 'Gemeindeteil', 'gemeindeteil_name': 'Buschmühlen',
       'gemeinde_name': 'Neubukow, Stadt'}, distance=0),
    R({'objektgruppe': 'Straße', 'strasse_name': 'Grüner Weg',
       'gemeinde_name': 'Neubukow, Stadt'}, distance=3),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Grüner Weg', 'hausnummer': '2',
       'gemeinde_name': 'Neubukow, Stadt', 'gemeindeteil_name': 'Buschmühlen'}, distance=22),
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Grüner Weg', 'hausnummer': '3',
       'gemeinde_name': 'Neubukow, Stadt', 'gemeindeteil_name': 'Buschmühlen'}, distance=30),
  ]

  assert_results(res, expected)


@pytest.mark.parametrize("out_epsg,expected_coord", [
  [None, [307680.447, 6004530.821]],
  [25833, [307680.447, 6004530.821]],
  [4326, [12.054841, 54.152802]],
  [3857, [1341938.79, 7199148.47]],
])
def test_out_epsg(client, out_epsg, expected_coord):
  """
  E.5.1 Koordinaten
  """
  kw = {'class': 'address'}
  if out_epsg:
    kw['out_epsg'] = out_epsg
  res = client.search('stettiner str 35 rostock', type='search', **kw)

  expected = [
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Stettiner Str.', 'hausnummer': '35',
       'gemeinde_name': 'Rostock, Hanse- und Universitätsstadt',
       'gemeindeteil_name': 'Lichtenhagen'}),
  ]
  assert_results(res, expected)
  assert res.features[0]['geometry']['coordinates'] == pytest.approx(expected_coord)


@pytest.mark.parametrize("term", [
  "kopernikusstr 46",
  "kopernikusstr. 46",
  "kopernikusstraße 46",
  "kopernikus straße 46",
  "kopernikus Straße 46",
  "KOPERNIKUS STRASSE 46",
])
def test_strasse_suffix(client, term):
  """
  Suchen mit 'straße' findet Ergebnisse mit str.
  """
  res = client.search(term, **{'class': 'address'})

  expected = [
    R({'objektgruppe': 'Adresse', 'strasse_name': 'Kopernikusstr.', 'hausnummer': '46',
       'gemeinde_name': 'Torgelow, Stadt', 'gemeindeteil_name': 'Torgelow'}),
  ]

  assert_results(res, expected)


def test_paging(client):
  query = 'parkentin, flur 1'
  min_total = 1000

  def check(limit, offset, expected):
    res = client.search(query, **{'class': 'parcel', 'limit': limit, 'offset': offset})
    assert_results(res, expected)
    assert res.doc['properties']['features_total'] >= min_total
    assert res.doc['properties']['features_returned'] == limit
    assert res.doc['properties']['features_offset'] == offset

  check(1, 0, [
    R({'objektgruppe': 'Flur', 'flur': '001', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'gemeinde_name': 'Bartenshagen-Parkentin'}),
  ])
  check(2, 0, [
    R({'objektgruppe': 'Flur', 'flur': '001', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'gemeinde_name': 'Bartenshagen-Parkentin'}),
    R({'objektgruppe': 'Flurstück', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'flurstueckskennzeichen': '132090-001-00001/0000'}),
  ])
  check(2, 1, [
    R({'objektgruppe': 'Flurstück', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'flurstueckskennzeichen': '132090-001-00001/0000'}),
    R({'objektgruppe': 'Flurstück', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'flurstueckskennzeichen': '132090-001-00002/0000'}),
  ])
  check(5, 0, [
    R({'objektgruppe': 'Flur', 'flur': '001', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'gemeinde_name': 'Bartenshagen-Parkentin'}),
    R({'objektgruppe': 'Flurstück', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'flurstueckskennzeichen': '132090-001-00001/0000'}),
    R({'objektgruppe': 'Flurstück', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'flurstueckskennzeichen': '132090-001-00002/0000'}),
    R({'objektgruppe': 'Flurstück', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'flurstueckskennzeichen': '132090-001-00003/0001'}),
    R({'objektgruppe': 'Flurstück', 'gemarkung_name': 'Parkentin',
       'gemarkung_schluessel': '132090', 'flurstueckskennzeichen': '132090-001-00003/0002'}),
  ])


class R(object):
  """
  R is an expected result for checks with assert_results.
  """

  def __init__(self, prop, distance=-1):
    self.prop = prop
    self.distance = distance


distance_property = 'entfernung'


def assert_results(res, expected):
  # __tracebackhide__ = True

  # print(res.doc)
  print(res.resp.url)
  assert not isinstance(res, Error), 'expected result got: {} ({})'.format(res.message, res.status)

  assert res.features

  fi = 0

  keys = {'_score_'}
  for e in expected:
    keys.update(e.prop.keys())

  for e in expected:
    print('searching for result:\n\t', e.prop)

    while True:
      assert fi < len(res.features), 'reached end of results while searching for {}'.format(e)
      prop = res.features[fi]['properties']
      print('compare?', dict((k, prop.get(k)) for k in keys))

      found = True

      for k, v in e.prop.items():
        if prop.get(k) != v:
          # property not found/matched
          found = False
          break
      fi += 1
      if found:
        if e.distance != -1:
          assert prop[distance_property] <= e.distance, 'distance for {}'.format(prop)
        break


HOST_BASE = "http://localhost:8521"


class ServerThread(threading.Thread):
  """
  Run WSGI server on a background thread.

  This thread starts a web server for a given WSGI application.
  """

  def __init__(self, app, hostbase=HOST_BASE):
    threading.Thread.__init__(self)
    self.app = app
    self.srv = None
    self.daemon = True
    self.hostbase = hostbase

  def run(self):
    """Start WSGI server on a background to listen to incoming."""

    from waitress import serve
    try:
      from urlparse import urlparse
    except ImportError:
      from urllib.parse import urlparse

    parts = urlparse(self.hostbase)
    domain, port = parts.netloc.split(":")

    try:
      serve(self.app, host='127.0.0.1', port=int(port), log_socket_errors=False, _quiet=True)
    except Exception:
      # We are a background thread so we have problems to interrupt tests in the case of error.
      # Try spit out something to the console.
      import traceback
      traceback.print_exc()


@pytest.fixture(scope='session')
def web_server(request, app):
  """py.test fixture to create a WSGI web server for functional tests.

  :param request: request
  :param app: py.test fixture for constructing a WSGI application

  :return: localhost URL where the web server is running.
  """

  server = ServerThread(app)
  server.start()

  # Wait randomish time to allows SocketServer to initialize itself.
  # Replace this with proper event telling the server is up.
  time.sleep(0.1)

  # assert server.srv is not None, "Could not start the test web server"

  host_base = HOST_BASE

  return host_base
