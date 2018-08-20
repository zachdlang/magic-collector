
from web.utility import *


def get():
	params = { 'app_id':g.config['OPENEXCHANGERATES_APPID'], 'base':'USD' }
	resp = requests.get('https://openexchangerates.org/api/latest.json', params=params)
	resp = json.loads(resp.text)
	return resp['rates']
