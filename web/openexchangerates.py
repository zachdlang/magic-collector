# Standard library imports
import requests
import json

# Local imports
from web import config


class OpenExchangeRatesException(Exception):
	pass


def get() -> dict:
	params = {'app_id': config.OPENEXCHANGERATES_APPID, 'base': 'USD'}
	response = requests.get(
		'https://openexchangerates.org/api/latest.json',
		params=params
	)
	response.raise_for_status()
	response = json.loads(response.text)
	return response['rates']
