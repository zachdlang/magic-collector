# Third party imports
from flask import session

# Local imports
from web import scryfall
from sitetools.utility import (
	fetch_query, mutate_query
)


def get_all(deleted):
	qry = """SELECT d.id, d.name, get_format(d.formatid) AS formatname,
				d.cardartid, c.id AS cardid, c.collectornumber,
				(SELECT code FROM card_set WHERE id = c.card_setid)
			FROM deck d
			LEFT JOIN card c ON (c.id = d.cardartid)
			WHERE d.deleted = %s AND d.userid = %s
			ORDER BY d.formatid, d.name"""
	qargs = (deleted, session['userid'],)
	decks = fetch_query(qry, qargs)
	return decks


def get(deckid):
	qry = """SELECT d.id, d.name, d.formatid, d.deleted,
				d.cardartid, c.id AS cardid, c.collectornumber,
				(SELECT code FROM card_SET WHERE id = c.card_setid)
			FROM deck d
			LEFT JOIN card c ON (c.id = d.cardartid)
			WHERE d.userid = %s AND d.id = %s"""
	qargs = (session['userid'], deckid,)
	result = fetch_query(qry, qargs, single_row=True)
	return result


def get_cards(deckid):
	qry = """SELECT dc.cardid, dc.quantity, dc.section,
				c.name, c.collectornumber,
				(SELECT code FROM card_set WHERE id = card_setid),
				has_deck_card(%s, dc.cardid) AS has_quantity
			FROM deck_card dc
			LEFT JOIN card c ON c.id = dc.cardid
			WHERE dc.deckid = %s
			AND (SELECT userid FROM deck WHERE id = dc.deckid) = %s"""
	qargs = (session['userid'], deckid, session['userid'],)
	cards = fetch_query(qry, qargs)

	return cards


def get_formats():
	formats = fetch_query("SELECT id, name FROM format ORDER BY id")
	return formats
