# Standard library imports
import re

# Third party imports
from flask import session, url_for

# Local imports
from flasktools.db import fetch_query, mutate_query


def get_all(deleted: bool) -> dict:
	decks = fetch_query(
		"""
		SELECT
			d.id, d.name, get_format(d.formatid) AS formatname,
			d.cardartid, d.cardartid AS cardid
		FROM deck d
		WHERE d.deleted = %s AND d.userid = %s
		ORDER BY d.formatid, d.name
		""",
		(deleted, session['userid'],)
	)
	for d in decks:
		# Temporary until I can incorporate this into the first query
		card = fetch_query(
			"""
			SELECT
				p.collectornumber, cs.code
			FROM printing p
			LEFT JOIN card_set cs ON (cs.id = p.card_setid)
			WHERE p.cardid = %s
			ORDER BY cs.released DESC LIMIT 1
			""",
			(d['cardid'],),
			single_row=True
		)
		if card:
			d['collectornumber'] = card['collectornumber']
			d['code'] = card['code']
	return decks


def get(deckid: int) -> dict:
	result = fetch_query(
		"""
		SELECT
			d.id, d.name, d.formatid, d.deleted,
			d.cardartid, d.cardartid AS cardid,
			d.notes
		FROM deck d
		WHERE d.userid = %s AND d.id = %s
		""",
		(session['userid'], deckid,),
		single_row=True
	)
	# Temporary until I can incorporate this into the first query
	card = fetch_query(
		"""
		SELECT
			p.collectornumber, cs.code
		FROM printing p
		LEFT JOIN card_set cs ON (cs.id = p.card_setid)
		WHERE p.cardid = %s
		ORDER BY cs.released DESC LIMIT 1
		""",
		(result['cardid'],),
		single_row=True
	)
	result['collectornumber'] = card['collectornumber']
	result['code'] = card['code']
	return result


def get_cards(deckid: int) -> tuple:
	qry = """SELECT dc.id, dc.cardid, dc.quantity, dc.section,
				c.name,
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


def get_formats() -> list:
	formats = fetch_query("SELECT id, name FROM format ORDER BY id")
	return formats


def parse_types(cards: list) -> list:
	prev_type = None
	new_rows = []
	for c in cards:
		if c['cardtype'] != prev_type:
			prev_type = c['cardtype']
			count = sum([x['quantity'] for x in cards if x.get('cardtype') == prev_type])
			new_rows.append({'is_type': True, 'label': prev_type, 'count': count})
		new_rows.append(c)

	return new_rows


def do_import(name: str, cards: list, notes: str = None) -> None:
	deckid = mutate_query(
		"""
		INSERT INTO deck (name, userid, formatid, notes)
		VALUES (
			COALESCE(%s, CONCAT('Imported Deck ', to_char(now(), 'YYYY-MM-DD HH12:MI:SS'))),
			%s,
			(SELECT id FROM format WHERE name = 'Other'),
			%s
		) RETURNING id
		""",
		(name, session['userid'], notes,),
		returning=True)['id']

	for c in cards:
		_import_card(deckid, c)

	qry = """UPDATE deck SET cardartid = (
				SELECT id FROM card WHERE EXISTS (
					SELECT 1 FROM deck_card WHERE cardid = card.id AND deckid = deck.id
				) ORDER BY random() LIMIT 1
			) WHERE id = %s"""
	mutate_query(qry, (deckid,))


def _import_card(deckid: int, card: dict) -> None:
	print('Importing deck card {}'.format(card['name']))
	mutate_query(
		"""
		INSERT INTO deck_card (deckid, cardid, quantity, section)
		VALUES (%s, deck_card_match(%s, %s), %s, %s)
		""",
		(deckid, card['name'], session['userid'], card['quantity'], card['section'],)
	)


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
