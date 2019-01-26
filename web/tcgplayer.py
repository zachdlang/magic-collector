
from web.utility import *


def login():
	headers = { 'Content-Type':'application/x-www-form-urlencoded' }
	data = { 'grant_type':'client_credentials', 'client_id':g.config['TCGPLAYER_PUBLICKEY'], 'client_secret':g.config['TCGPLAYER_PRIVATEKEY'] }
	resp = requests.post('https://api.tcgplayer.com/token', data=data, headers=headers)
	resp = json.loads(resp.text)
	session['tcgplayer_bearertoken'] = resp['access_token']


def search_categories():
	if 'tcgplayer_bearertoken' not in session:
		login()
	headers = { 'Authorization':'bearer %s' % session['tcgplayer_bearertoken'] }
	resp = requests.get('http://api.tcgplayer.com/catalog/categories/1/search/manifest', headers=headers)
	resp = json.loads(resp.text)
	for r in resp['results'][0]['filters']:
		if r['name'] == 'SetName':
			for i in r['items']:
				print(i)


def search(card):
	productid = None
	if 'tcgplayer_bearertoken' not in session:
		login()

	# check for multiface card format
	if ' // ' in card['name']:
		card['name'] = card['name'].split(' // ')[0]

	headers = {'Content-Type': 'application/json', 'Authorization': 'bearer %s' % session['tcgplayer_bearertoken']}
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
			{
				'name': 'Rarity',
				'values': [card['rarity']]
			}
		]
	}

	resp = requests.post('http://api.tcgplayer.com/catalog/categories/1/search', data=json.dumps(data), headers=headers)
	search_results = json.loads(resp.text)['results']
	if len(search_results) == 1:
		productid = search_results[0]
	elif len(search_results) > 1:
		# filter down from product details
		resp = requests.get('http://api.tcgplayer.com/catalog/products/%s' % ','.join([str(r) for r in search_results]), params={'getExtendedFields': True}, headers=headers)
		product_results = json.loads(resp.text)['results']
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
			print('Extra product search found result %s for %s %s' % (productid, card['name'], card['set_name']))
		else:
			# filter down from set details
			resp = requests.get('http://api.tcgplayer.com/catalog/groups/%s' % ','.join([str(r['groupId']) for r in products_found]), headers=headers)
			group_results = json.loads(resp.text)['results']
			groups_found = []
			for r in group_results:
				for p in products_found:
					if str(r['groupId']) == str(p['groupId']):
						groups_found.append(p)
			if len(groups_found) == 1:
				productid = groups_found[0]['productId']
				print('Extra group search found result %s for %s %s' % (productid, card['name'], card['set_name']))
		if productid is None:
			print('MORE THAN ONE RESULT (%s) %s %s %s' % (len(search_results), card['name'], card['set_name'], card['rarity']))
	else:
		print('NO RESULT %s %s %s' % (card['name'], card['set_name'], card['rarity']))
	return productid


def get_price(cards):
	if 'tcgplayer_bearertoken' not in session:
		login()
	print('Fetching prices for %s cards' % len(cards))
	if len(cards) == 0:
		print('Ignoring 0 length');
		return {}
	headers = { 'Authorization':'bearer %s' % session['tcgplayer_bearertoken'] }
	resp = requests.get('http://api.tcgplayer.com/pricing/product/%s' % ','.join([ cards[cardid] for cardid in cards ]), headers=headers)
	resp = json.loads(resp.text)
	prices = { cardid:{ 'normal':None, 'foil':None } for cardid, productid in cards.items() }
	for cardid, productid in cards.items():
		for r in resp['results']:
			if str(r['productId']) == productid:
				if r['subTypeName'] == 'Normal':
					prices[cardid]['normal'] = r['midPrice']
				elif r['subTypeName'] == 'Foil':
					prices[cardid]['foil'] = r['midPrice']
				else:
					print('UNKNOWN SUBTYPE %s %s' % (cards, r['subTypeName']))
	return prices
