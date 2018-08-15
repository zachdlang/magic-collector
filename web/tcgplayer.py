
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


def search(cardname, setname):
	prices = None
	if 'tcgplayer_bearertoken' not in session:
		login()

	# check for multiface card format
	if ' // ' in cardname:
		cardname = cardname.split(' // ')[0]

	headers = { 'Content-Type':'application/json', 'Authorization':'bearer %s' % session['tcgplayer_bearertoken'] }
	data = { 'filters':[{ 'name': 'ProductName', 'values': [ cardname ] }, { 'name':'SetName', 'values': [ setname ] }] }
	resp = requests.post('http://api.tcgplayer.com/catalog/categories/1/search', data=json.dumps(data), headers=headers)
	resp = json.loads(resp.text)
	if len(resp['results']) == 1:
		prices = get_price(resp['results'][0])
	elif len(resp['results']) > 1:
		print('MORE THAN ONE RESULT %s %s' % (cardname, setname))
	else:
		print('NO RESULT %s %s' % (cardname, setname))
	return prices


def get_price(productid):
	prices = { 'normal':None, 'foil':None }
	if 'tcgplayer_bearertoken' not in session:
		login()
	headers = { 'Authorization':'bearer %s' % session['tcgplayer_bearertoken'] }
	resp = requests.get('http://api.tcgplayer.com/pricing/product/%s' % productid, headers=headers)
	resp = json.loads(resp.text)
	for r in resp['results']:
		if r['subTypeName'] == 'Normal':
			prices['normal'] = r['midPrice']
		elif r['subTypeName'] == 'Foil':
			prices['foil'] = r['midPrice']
		else:
			print('UNKNOWN SUBTYPE %s %s' % (productid, r['subTypeName']))
	return prices
