
from web.utility import *


def get():
	# Save into session to lessen API requests
	if 'currency' in session:
		currency = session['currency']
	else:
		currency = { 'code':'NZD' }
		params = { 'app_id':g.config['OPENEXCHANGERATES_APPID'], 'base':'USD' }
		resp = requests.get('https://openexchangerates.org/api/latest.json', params=params)
		resp = json.loads(resp.text)
		currency['rate'] = resp['rates'][currency['code']]
		session['currency'] = currency
	return currency
