
from web.utility import *


def scryfall_request(endpoint, params=None, data=None, post=False):
	func = requests.get
	if post is True:
		func = requests.post
	r = func('https://api.scryfall.com%s' % endpoint, params=params, data=data, headers={ 'Content-Type':'application/json' }).text
	resp = json.loads(r)
	return resp


def search(name):
	params = { 'q':name, 'unique':'prints' }
	resp = scryfall_request('/cards/search', params=params)
	simple_resp = []
	for r in resp['data']:
		if r['multiverseid']:
			simple_resp.append(simplify(r))
	return simple_resp


def get(multiverseid):
	resp = scryfall_request('/cards/multiverse/%s' % multiverseid)
	return simplify(resp)


def get_bulk(multiverseids):
	data = { 'identifiers':[ { 'multiverse_id':x } for x in multiverseids ] }
	resp = scryfall_request('/cards/collection', data=json.dumps(data), post=True)
	simple_resp = []
	if resp['not_found']:
		raise Exception('Not found: %s' % resp['not_found'])
	for r in resp['data']:
		simple_resp.append(simplify(r))
	return simple_resp


def simplify(resp):
	simple = {
		'name': resp['name'],
		'multiverseid': resp['multiverse_ids'][0],
		'rarity': resp['rarity'].upper()[0],
		'set': resp['set'].upper(),
		'set_name': resp['set_name'],
		'collectornumber': resp['collector_number'],
		'multifaced': False
	}
	if 'colors' in resp:
		simple['colors'] = ''.join(resp['colors'])

	if resp.get('card_faces'):
		resp = resp['card_faces'][0]
		simple['multifaced'] = True

	if 'colors' not in simple:
		simple['colors'] = ''.join(resp['colors'])

	simple['image_manual'] = 'https://img.scryfall.com/cards/normal/en/%s/%s.jpg' % (simple['set'].lower(), simple['collectornumber'])

	return simple
