# Third party imports
from flask import session

# Local imports
from sitetools.utility import fetch_query


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
				total_printings_owned(d.userid, dc.cardid) AS has_quantity,
				c.typeline, c.manacost
			FROM deck_card dc
			LEFT JOIN deck d ON (d.id = dc.deckid)
			LEFT JOIN card c ON (c.id = dc.cardid)
			WHERE d.id = %s
			AND d.userid = %s
			ORDER BY CASE WHEN NOT is_basic_land(c.id) THEN 1 ELSE 2 END"""
	qargs = (deckid, session['userid'],)
	cards = fetch_query(qry, qargs)

	return cards


def get_formats():
	formats = fetch_query("SELECT id, name FROM format ORDER BY id")
	return formats
