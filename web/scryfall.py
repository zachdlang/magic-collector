# Standard library imports
import requests
import json
import os

# Third party imports
from flask import url_for

# Local imports
from sitetools.utility import (
	get_static_file, fetch_image
)


def send_request(endpoint, params=None, data=None, post=False):
	func = requests.get
	if post is True:
		func = requests.post
	r = func('https://api.scryfall.com%s' % endpoint, params=params, data=data, headers={'Content-Type': 'application/json'}).text
	resp = json.loads(r)
	return resp


def search(name):
	params = {'q': name, 'unique': 'prints'}
	resp = send_request('/cards/search', params=params)
	simple_resp = []
	if resp.get('code') != 'not_found':
		for r in resp['data']:
			simple_resp.append(simplify(r))
	return simple_resp


def get_set(code):
	endpoint = '/sets/%s' % code if code is not None else '/sets'
	resp = send_request(endpoint)
	return resp


def get(code, collectornumber):
	resp = send_request('/cards/%s/%s' % (code.lower(), collectornumber))
	return simplify(resp)


def get_bulk(multiverseids):
	data = {'identifiers': [{'multiverse_id': x} for x in multiverseids]}
	resp = send_request('/cards/collection', data=json.dumps(data), post=True)
	simple_resp = []
	if resp['not_found']:
		raise Exception('Not found: %s' % resp['not_found'])
	for r in resp['data']:
		simple_resp.append(simplify(r))
	return simple_resp


def bulk_file_import(filename):
	with open(filename) as f:
		data = json.loads(f.read())
	simple_resp = []
	for r in data:
		simple_resp.append(simplify(r))
	return simple_resp


def simplify(resp):
	simple = {
		'name': resp['name'],
		'multiverseid': None,
		'rarity': resp['rarity'].upper()[0],
		'set': resp['set'].upper(),
		'set_name': resp['set_name'],
		'collectornumber': resp['collector_number'],
		'multifaced': False,
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

	return simple
