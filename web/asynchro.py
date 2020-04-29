# Standard library imports
import os

# Local imports
from web import (
	app, scryfall, tcgplayer, openexchangerates, collection,
	config
)
from flasktools import get_static_file, fetch_image
from flasktools.celery import setup_celery
from flasktools.db import mutate_query
import rollbar
from celery.signals import task_failure

celery = setup_celery(app)


@task_failure.connect
def handle_task_failure(**kwargs):
	if not hasattr(config, 'TESTMODE'):
		env = 'production' if not hasattr(config, 'TESTMODE') else 'development'
		rollbar.init(
			config.ROLLBAR_TOKEN,
			environment=env
		)

		def celery_base_data_hook(request, data):
			data['framework'] = 'celery'

		rollbar.BASE_DATA_HOOK = celery_base_data_hook

		rollbar.report_exc_info(extra_data=kwargs)


def set_icon_filename(code: str) -> str:
	return get_static_file('/images/set_icon_{}.svg'.format(code))


@celery.task(queue='collector')
def get_set_icon(code: str) -> None:
	filename = set_icon_filename(code)
	if not os.path.exists(filename):
		try:
			url = scryfall.get_set(code)['icon_svg_uri']
			fetch_image(filename, url)
		except scryfall.NotFound:
			pass


def card_art_filename(cardid: int) -> str:
	return get_static_file('/images/card_art_{}.jpg'.format(cardid))


@celery.task(queue='collector')
def get_card_art(cardid: int, code: str, collectornumber: str) -> None:
	filename = card_art_filename(cardid)
	if not os.path.exists(filename):
		url = scryfall.get(code, collectornumber)['arturl']
		fetch_image(filename, url)


def card_image_filename(cardid: int) -> str:
	return get_static_file('/images/card_image_{}.jpg'.format(cardid))


@celery.task(queue='collector')
def get_card_image(cardid: int, code: str, collectornumber: str) -> None:
	filename = card_image_filename(cardid)
	if not os.path.exists(filename):
		try:
			url = scryfall.get(code, collectornumber)['imageurl']
			fetch_image(filename, url)
		except scryfall.NotFound:
			pass


@celery.task(queue='collector')
def fetch_prices(cards: list, tcgplayer_token: str) -> None:
	# Filter out cards without tcgplayerid to save requests
	cards = [c for c in cards if c['productid'] is not None]
	bulk_lots = ([cards[i:i + 250] for i in range(0, len(cards), 250)])
	for lot in bulk_lots:
		card_dict = {
			str(c['id']): str(c['productid'])
			for c in lot
			if c['productid'] is not None
		}
		prices = tcgplayer.get_price(
			card_dict,
			token=tcgplayer_token
		)
		set_prices(prices)
	print('Price update completed.')

	# Try to match up cards without TCGPlayer IDs
	for c in cards:
		if c['productid'] is None:
			print(f"Searching for TCGPlayer ID for {c['name']} ({c['set_name']}).")
			c['productid'] = tcgplayer.search(c, token=tcgplayer_token)
			if c['productid'] is not None:
				mutate_query(
					"UPDATE printing SET tcgplayer_productid = %s WHERE id = %s",
					(c['productid'], c['id'],)
				)


def set_prices(prices):
	updates = []
	for cardid, price in prices.items():
		# Only update if we received have prices
		if price['normal'] is not None or price['foil'] is not None:
			updates.append({
				'price': price['normal'],
				'foilprice': price['foil'],
				'pricetype': price['type'],
				'id': cardid
			})

	print('Updating prices for {} cards.'.format(len(updates)))
	mutate_query(
		"""
		SELECT set_price(
			%(id)s,
			%(price)s::MONEY,
			%(foilprice)s::MONEY,
			%(pricetype)s)
		""",
		updates,
		executemany=True
	)


@celery.task(queue='collector')
def fetch_rates() -> None:
	print('Fetching exchange rates')
	rates = openexchangerates.get()
	updates = [{'code': code, 'rate': rate} for code, rate in rates.items()]
	mutate_query(
		"SELECT update_rates(%(code)s, %(rate)s)",
		updates,
		executemany=True
	)
	print('Updated exchange rates')


@celery.task(queue='collector')
def refresh_from_scryfall(query: str) -> None:
	resp = scryfall.search(query)
	collection.import_cards(resp)
