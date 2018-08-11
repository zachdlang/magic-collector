
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
		simple_resp.append(simplify(r))
	return simple_resp


def get(multiverse_id):
	resp = scryfall_request('/cards/multiverse/%s' % multiverse_id)
	return simplify(resp)


def get_bulk(multiverse_ids):
	data = { 'identifiers':multiverse_ids }
	resp = scryfall_request('/cards/collection', data=json.dumps(data), post=True)
	simple_resp = []
	for r in resp['data']:
		simple_resp.append(simplify(r))
	return simple_resp


def simplify(resp):
	simple = {
		'multiverse_ids': resp['multiverse_ids'][0],
		'rarity': resp['rarity'].upper()[0],
		'set': resp['set'].upper(),
		'set_name': resp['set_name'],
		'cmc': resp['cmc']
	}

	if resp.get('card_faces'):
		resp = resp['card_faces'][0]

	simple['name'] = resp['name']
	simple['colors'] = ''.join(resp['colors'])
	simple['mana_cost'] = resp['mana_cost']
	simple['power'] = resp.get('power')
	simple['toughness'] = resp.get('toughness')
	simple['image'] = resp['image_uris']['normal']

	return simple
