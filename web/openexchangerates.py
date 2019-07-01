# Standard library imports
import requests
import json

# Local imports
from web import config


def get():
	params = {'app_id': config.OPENEXCHANGERATES_APPID, 'base': 'USD'}
	resp = requests.get('https://openexchangerates.org/api/latest.json', params=params)
	resp = json.loads(resp.text)
	return resp['rates']
