# Standard library imports
import requests
import json

# Third party imports
from flask import current_app as app


def get():
	params = {'app_id': app.config['OPENEXCHANGERATES_APPID'], 'base': 'USD'}
	resp = requests.get('https://openexchangerates.org/api/latest.json', params=params)
	resp = json.loads(resp.text)
	return resp['rates']
