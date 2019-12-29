# Standard library imports
import requests
import json

# Local imports
from web import config


class TCGPlayerException(Exception):
	pass


def _send_request(
	endpoint: str,
	params: any = None,
	data: any = None,
	headers: dict = None,
	post: bool = False
) -> any:
	func = requests.get
	if post is True:
		func = requests.post
	response = func(
		'https://api.tcgplayer.com{}'.format(endpoint),
		params=params,
		data=data,
		headers=headers
	)
	response.raise_for_status()
	resp = json.loads(response.text)
	return resp


def _auth_header(token: str) -> str:
	return {'Authorization': 'bearer {}'.format(token)}


def login() -> str:
	headers = {'Content-Type': 'application/x-www-form-urlencoded'}
	data = {
		'grant_type': 'client_credentials',
		'client_id': config.TCGPLAYER_PUBLICKEY,
		'client_secret': config.TCGPLAYER_PRIVATEKEY
	}
	resp = _send_request(
		'/token',
		data=data,
		headers=headers,
		post=True
	)

	return resp['access_token']


def search_categories(token: str = None) -> str:
	if token is None:
		token = login()
	headers = _auth_header(token)
	resp = _send_request(
		'/catalog/categories/1/search/manifest',
		headers=headers
	)
	for r in resp['results'][0]['filters']:
		if r['name'] == 'SetName':
			for i in r['items']:
				print(i)


def search(card, token=None):
	if token is None:
		token = login()

	productid = None
	# check for multiface card format
	if ' // ' in card['name']:
		card['name'] = card['name'].split(' // ')[0]

	headers = _auth_header(token)
	headers['Content-Type'] = 'application/json'
	data = {
		'filters': [
			{
				'name': 'ProductName',
				'values': [card['name']]
			},
			{
				'name': 'SetName',
				'values': [card['set_name']]
			},
			# Comment out rarity for fetching promos
			{
				'name': 'Rarity',
				'values': [card['rarity']]
			}
		]
	}

	resp = _send_request(
		'/catalog/categories/1/search',
		data=json.dumps(data),
		headers=headers,
		post=True
	)
	search_results = resp['results']
	if len(search_results) == 1:
		productid = search_results[0]
	elif len(search_results) > 1:
		# filter down from product details
		resp = _send_request(
			'/catalog/products/{}'.format(
				','.join([str(r) for r in search_results])
			),
			params={'getExtendedFields': True},
			headers=headers
		)
		product_results = resp['results']
		products_found = []
		for r in product_results:
			check_this = False
			if 'productConditions' in r:
				for pc in r['productConditions']:
					if pc['language'] == 'English':
						check_this = True
			else:
				# No multiple languages, just check this result
				check_this = True

			if check_this is True:
				# Check against collector number
				for ex in r['extendedData']:
					if ex['name'] == 'Number' and str(ex['value']) == str(card['collectornumber']):
						products_found.append(r)
		if len(products_found) == 1:
			productid = products_found[0]['productId']
			print(
				'Extra product search found result {} for {} {}'.format(
					productid,
					card['name'],
					card['set_name']
				)
			)
		else:
			# filter down from set details
			group_params = ','.join([str(r['groupId']) for r in products_found])
			resp = _send_request(
				'/catalog/groups/{}'.format(group_params),
				headers=headers
			)
			group_results = resp['results']
			groups_found = []
			for r in group_results:
				for p in products_found:
					if str(r['groupId']) == str(p['groupId']) and r['abbreviation'] == card['set_code']:
						groups_found.append(p)
			if len(groups_found) == 1:
				productid = groups_found[0]['productId']
				print(
					'Extra group search found result {} for {} {}'.format(
						productid,
						card['name'],
						card['set_name']
					)
				)
		if productid is None:
			print(
				'MORE THAN ONE RESULT ({}) {} {} {}'.format(
					len(search_results),
					card['name'],
					card['set_name'],
					card['rarity']
				)
			)
	else:
		print(
			'NO RESULT {} {} {}'.format(
				card['name'],
				card['set_name'],
				card['rarity']
			)
		)
	return productid


def get_price(cards: list, token: str = None) -> dict:
	if token is None:
		token = login()
	print('Fetching prices for {} cards.'.format(len(cards)))
	if len(cards) == 0:
		print('Ignoring 0 length')
		return {}
	headers = _auth_header(token)
	card_params = ','.join([cards[cardid] for cardid in cards])
	resp = _send_request(
		'/pricing/product/{}'.format(card_params),
		headers=headers
	)
	prices = {cardid: {'normal': None, 'foil': None, 'type': None} for cardid, productid in cards.items()}
	for cardid, productid in cards.items():
		for r in resp['results']:
			if str(r['productId']) == productid:
				# Fall back to market (recent sale) price if no mid (current sale) price
				price_found = r['midPrice']
				prices[cardid]['type'] = 'mid'
				if price_found is None:
					price_found = r['marketPrice']
					prices[cardid]['type'] = 'market'
				if r['subTypeName'] == 'Normal':
					prices[cardid]['normal'] = price_found
				elif r['subTypeName'] == 'Foil':
					prices[cardid]['foil'] = price_found
				else:
					print('UNKNOWN SUBTYPE {} {}'.format(cards, r['subTypeName']))
	return prices
