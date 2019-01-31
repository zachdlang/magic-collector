# Third party imports
from flask import session

# Local imports
from sitetools.utility import (
	fetch_query, mutate_query
)


def get_all():
	decks = fetch_query("SELECT id, name FROM deck WHERE userid = %s", (session['userid'],))
	return decks


def get_cards(deckid):
	qry = "SELECT cardid, quantity FROM deck_card WHERE id = %s AND userid = %s"
	qargs = (deckid, session['userid'],)
	cards = fetch_query(qry, qargs)
	return cards
