# Standard library imports
import requests
import json

# Local imports
from web import config


class OpenExchangeRatesException(Exception):
	pass


def get() -> dict:
	params = {'app_id': config.OPENEXCHANGERATES_APPID, 'base': 'USD'}
	resp = requests.get('https://openexchangerates.org/api/latest.json', params=params)
	response.raise_for_status()
	resp = json.loads(resp.text)
	return resp['rates']
