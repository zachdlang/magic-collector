# Standard library imports
import os

# Local imports
from web import (
	app, scryfall, tcgplayer, openexchangerates, collection
)
from sitetools.utility import (
	setup_celery, get_static_file, fetch_image, mutate_query
)

celery = setup_celery(app)


def set_icon_filename(code):
	return get_static_file('/images/set_icon_{}.svg'.format(code))


@celery.task(queue='collector')
def get_set_icon(code):
	filename = set_icon_filename(code)
	if not os.path.exists(filename):
		url = scryfall.get_set(code)['icon_svg_uri']
		fetch_image(filename, url)


def card_art_filename(cardid):
	return get_static_file('/images/card_art_{}.jpg'.format(cardid))


@celery.task(queue='collector')
def get_card_art(cardid, code, collectornumber):
	filename = card_art_filename(cardid)
	if not os.path.exists(filename):
		url = scryfall.get(code, collectornumber)['arturl']
		fetch_image(filename, url)


def card_image_filename(cardid):
	return get_static_file('/images/card_image_{}.jpg'.format(cardid))


@celery.task(queue='collector')
def get_card_image(cardid, code, collectornumber):
	filename = card_image_filename(cardid)
	if not os.path.exists(filename):
		url = scryfall.get(code, collectornumber)['imageurl']
		fetch_image(filename, url)


@celery.task(queue='collector')
def fetch_prices(cards, tcgplayer_token):
	for c in cards:
		if c['productid'] is None:
			print('Searching for TCGPlayer ID for {} ({}).'.format(c['name'], c['set_name']))
			c['productid'] = tcgplayer.search(c, token=tcgplayer_token)
			if c['productid'] is not None:
				mutate_query("UPDATE card SET tcgplayer_productid = %s WHERE id = %s", (c['productid'], c['id'],))

	# Filter out cards without tcgplayerid to save requests
	cards = [c for c in cards if c['productid'] is not None]
	bulk_lots = ([cards[i:i + 250] for i in range(0, len(cards), 250)])
	prices = {}
	for lot in bulk_lots:
		prices.update(tcgplayer.get_price({str(c['id']): str(c['productid']) for c in lot if c['productid'] is not None}, token=tcgplayer_token))

	updates = []
	for cardid, price in prices.items():
		# Only update if we received have prices
		if price['normal'] is not None or price['foil'] is not None:
			updates.append({'price': price['normal'], 'foilprice': price['foil'], 'id': cardid})
	mutate_query(
		"UPDATE card SET price = %(price)s, foilprice = %(foilprice)s WHERE id = %(id)s",
		updates,
		executemany=True
	)
	mutate_query(
		"""
		INSERT INTO price_history (cardid, price, foilprice)
		SELECT %(id)s, %(price)s, %(foilprice)s
		WHERE NOT EXISTS (
			SELECT 1 FROM price_history WHERE cardid = %(id)s AND created = current_date
		)
		""",
		updates,
		executemany=True
	)
	print('Updated prices for {} cards.'.format(len(updates)))


@celery.task(queue='collector')
def fetch_rates():
	print('Fetching exchange rates')
	rates = openexchangerates.get()
	updates = [{'code': code, 'rate': rate} for code, rate in rates.items()]
	mutate_query("SELECT update_rates(%(code)s, %(rate)s)", updates, executemany=True)
	print('Updated exchange rates')


@celery.task(queue='collector')
def refresh_from_scryfall(query):
	resp = scryfall.search(query)
	collection.import_cards(resp)
