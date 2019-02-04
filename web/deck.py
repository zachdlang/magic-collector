# Third party imports
from flask import session

# Local imports
from web import scryfall
from sitetools.utility import (
	fetch_query, mutate_query
)


def get_all(deleted):
	qry = "SELECT id, name, arturl FROM deck WHERE deleted = %s AND userid = %s"
	qargs = (deleted, session['userid'],)
	decks = fetch_query(qry, qargs)
	return decks


def get(deckid):
	qry = "SELECT id, name, arturl FROM deck WHERE userid = %s AND id = %s"
	qargs = (session['userid'], deckid,)
	result = fetch_query(qry, qargs, single_row=True)
	return result


def get_image(deckid):
	qry = "SELECT multiverseid FROM card WHERE id = (SELECT cardid FROM deck_card WHERE deckid = %s ORDER BY id LIMIT 1)"
	imgcard = fetch_query(qry, (deckid,), single_row=True)
	return scryfall.get(imgcard['multiverseid'])['arturl']


def get_cards(deckid):
	qry = "SELECT cardid, quantity FROM deck_card WHERE id = %s AND (SELECT userid FROM deck WHERE id = deckid) = %s"
	qargs = (deckid, session['userid'],)
	cards = fetch_query(qry, qargs)
	return cards
