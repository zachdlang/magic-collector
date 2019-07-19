# Standard library imports
import re

# Third party imports
from flask import session, url_for

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
	qry = """SELECT dc.id, dc.cardid, dc.quantity, dc.section,
				c.name, c.collectornumber,
				(SELECT code FROM card_set WHERE id = card_setid),
				total_printings_owned(d.userid, dc.cardid) AS has_quantity,
				c.typeline, c.manacost, COALESCE(t.name, 'Other') AS cardtype,
				is_basic_land(c.id) AS basic_land
			FROM deck_card dc
			LEFT JOIN deck d ON (d.id = dc.deckid)
			LEFT JOIN card c ON (c.id = dc.cardid)
			LEFT JOIN card_type t ON (t.id = c.card_typeid)
			WHERE d.id = %s
			AND d.userid = %s
			ORDER BY card_typeid, is_basic_land(c.id), c.name"""
	qargs = (deckid, session['userid'],)
	cards = fetch_query(qry, qargs)

	main, sideboard = [], []
	for c in cards:
		manasymbols = []
		if c['manacost'] is not None:
			for sym in re.findall(r'{[A-Z0-9/]+}', c['manacost']):
				if sym in MANASYMBOL_IMG:
					filename = 'symbols/{}'.format(MANASYMBOL_IMG[sym])
					manasymbols.append(url_for('static', filename=filename))
				else:
					manasymbols.append(sym)
		c['manacost'] = manasymbols

		c['insufficient_quantity'] = c['has_quantity'] < c['quantity']
		if c['basic_land']:
			c['has_quantity'] = None
			c['insufficient_quantity'] = False

		if c['section'] == 'main':
			main.append(c)
		elif c['section'] == 'sideboard':
			sideboard.append(c)

	return main, sideboard


def get_formats():
	formats = fetch_query("SELECT id, name FROM format ORDER BY id")
	return formats


def parse_types(cards):
	prev_type = None
	new_rows = []
	for c in cards:
		if c['cardtype'] != prev_type:
			prev_type = c['cardtype']
			count = sum([x['quantity'] for x in cards if x.get('cardtype') == prev_type])
			new_rows.append({'is_type': True, 'label': prev_type, 'count': count})
		new_rows.append(c)

	return new_rows


MANASYMBOL_IMG = {
	'{X}': 'X.svg',
	'{0}': '0.svg',
	'{1}': '1.svg',
	'{2}': '2.svg',
	'{3}': '3.svg',
	'{4}': '4.svg',
	'{5}': '5.svg',
	'{6}': '6.svg',
	'{7}': '7.svg',
	'{8}': '8.svg',
	'{9}': '9.svg',
	'{10}': '10.svg',
	'{11}': '11.svg',
	'{12}': '12.svg',
	'{13}': '13.svg',
	'{14}': '14.svg',
	'{15}': '15.svg',
	'{16}': '16.svg',
	'{W/U}': 'WU.svg',
	'{W/B}': 'WB.svg',
	'{B/R}': 'BR.svg',
	'{B/G}': 'BG.svg',
	'{U/B}': 'UB.svg',
	'{U/R}': 'UR.svg',
	'{R/G}': 'RG.svg',
	'{R/W}': 'RW.svg',
	'{G/W}': 'GW.svg',
	'{G/U}': 'GU.svg',
	'{2/W}': '2W.svg',
	'{2/U}': '2U.svg',
	'{2/B}': '2B.svg',
	'{2/R}': '2R.svg',
	'{2/G}': '2G.svg',
	'{P}': 'P.svg',
	'{W/P}': 'WP.svg',
	'{U/P}': 'UP.svg',
	'{B/P}': 'BP.svg',
	'{R/P}': 'RP.svg',
	'{G/P}': 'GP.svg',
	'{W}': 'W.svg',
	'{U}': 'U.svg',
	'{B}': 'B.svg',
	'{R}': 'R.svg',
	'{G}': 'G.svg',
	'{C}': 'C.svg',
	'{S}': 'S.svg'
}
