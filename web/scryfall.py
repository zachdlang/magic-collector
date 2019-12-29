# Standard library imports
import requests
import json


class ScryfallException(Exception):
	pass


def _send_request(
	endpoint: str,
	params: any = None,
	data: any = None,
	post: bool = False
) -> any:
	func = requests.get
	if post is True:
		func = requests.post
	response = func(
		'https://api.scryfall.com{}'.format(endpoint),
		params=params,
		data=data,
		headers={'Content-Type': 'application/json'}
	)
	response.raise_for_status()
	resp = json.loads(response.text)
	return resp


def search(name: str) -> list:
	params = {'q': name, 'unique': 'prints'}
	resp = _send_request('/cards/search', params=params)
	simple_resp = []
	if resp.get('code') != 'not_found':
		for r in resp['data']:
			simple_resp.append(simplify(r))
	return simple_resp


def get_set(code: str) -> dict:
	endpoint = '/sets'
	if code is not None:
		endpoint += '/{}'.format(code)
	resp = _send_request(endpoint)
	return resp


def get(code: str, collectornumber: str) -> list:
	resp = _send_request('/cards/{}/{}'.format(code.lower(), collectornumber))
	return simplify(resp)


def get_bulk(scryfall_ids: list) -> list:
	data = {'identifiers': [{'id': x} for x in scryfall_ids]}
	resp = _send_request('/cards/collection', data=json.dumps(data), post=True)
	simple_resp = []
	if resp['not_found']:
		raise ScryfallException('Not found: {}'.format(resp['not_found']))
	for r in resp['data']:
		simple_resp.append(simplify(r))
	return simple_resp


def bulk_file_import(filename: str) -> list:
	with open(filename) as f:
		data = json.loads(f.read())
	simple_resp = []
	for r in data:
		simple_resp.append(simplify(r))
	return simple_resp


def simplify(resp: dict) -> dict:
	simple = {
		'name': resp['name'],
		'multiverseid': None,
		'scryfallid': resp['id'],
		'rarity': resp['rarity'].upper()[0],
		'set': resp['set'].upper(),
		'set_name': resp['set_name'],
		'collectornumber': resp['collector_number'],
		'multifaced': False,
		'cmc': resp['cmc'],
		'typeline': resp['type_line'],
		'language': resp['lang'],
		'manacost': resp.get('mana_cost')
	}

	if resp['multiverse_ids']:
		simple['multiverseid'] = resp['multiverse_ids'][0]

	# These should catch normal & split cards
	if 'colors' in resp:
		simple['colors'] = ''.join(resp['colors'])
	if 'image_uris' in resp:
		simple['imageurl'] = resp['image_uris']['normal']
		simple['arturl'] = resp['image_uris']['art_crop']

	if resp.get('card_faces'):
		resp = resp['card_faces'][0]
		simple['multifaced'] = True

		# These should catch double-sided cards
		if 'colors' not in simple:
			simple['colors'] = ''.join(resp['colors'])
		if 'imageurl' not in simple:
			simple['imageurl'] = resp['image_uris']['normal']
			simple['arturl'] = resp['image_uris']['art_crop']
		if simple['manacost'] is None:
			simple['manacost'] = resp.get('mana_cost')

	return simple
