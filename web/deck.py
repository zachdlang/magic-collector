# Third party imports
from flask import session

# Local imports
from web import scryfall
from sitetools.utility import (
	fetch_query, mutate_query
)


def get_all():
	decks = fetch_query("SELECT id, name, arturl FROM deck WHERE userid = %s", (session['userid'],))
	return decks


def get_image(deckid):
	qry = "SELECT multiverseid FROM card WHERE id = (SELECT cardid FROM deck_card WHERE deckid = %s ORDER BY id LIMIT 1)"
	imgcard = fetch_query(qry, (deckid,), single_row=True)
	return scryfall.get(imgcard['multiverseid'])['arturl']


def get_cards(deckid):
	qry = "SELECT cardid, quantity FROM deck_card WHERE id = %s AND userid = %s"
	qargs = (deckid, session['userid'],)
	cards = fetch_query(qry, qargs)
	return cards
