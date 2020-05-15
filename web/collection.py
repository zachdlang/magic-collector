# Third party imports
from flask import session

# Local imports
from web import scryfall, tcgplayer, functions
from flasktools import strip_unicode_characters, serve_static_file
from flasktools.db import fetch_query, mutate_query


def get(params: dict) -> dict:
	resp = {}

	limit = 20
	page = 1
	if params.get('page'):
		page = int(params.get('page'))
	offset = page * limit - limit

	# Sorting
	cols = {
		'name': 'c.name',
		'setname': 'cs.released',
		'rarity': "get_rarity_sort(p.rarity)",
		'quantity': 'uc.quantity',
		'foil': 'uc.foil',
		'price': 'get_price(uc.id)'
	}
	sort = cols.get(params.get('sort'), 'c.name')
	descs = {'asc': 'ASC', 'desc': 'DESC'}
	sort_desc = descs.get(params.get('sort_desc'), 'ASC')

	# Filters
	search = f"%{params['filter_search']}%" if params['filter_search'] else None
	filters = {
		'search': search,
		'set': params.get('filter_set'),
		'rarity': params.get('filter_rarity')
	}

	qry = """SELECT count(1) AS count,
				sum(uc.quantity) AS sum,
				sum(uc.quantity * get_price(uc.id)) AS sumprice
			FROM user_card uc
			LEFT JOIN printing p ON (p.id = uc.printingid)
			WHERE uc.userid = %s"""
	qargs = (session['userid'],)
	if filters['search']:
		qry += " AND (SELECT name FROM card WHERE id = p.cardid) ILIKE %s"
		qargs += (filters['search'],)
	if filters['set']:
		qry += " AND p.card_setid = %s"
		qargs += (filters['set'],)
	if filters['rarity']:
		qry += " AND p.rarity = %s"
		qargs += (filters['rarity'],)
	aggregate = fetch_query(qry, qargs, single_row=True)
	resp['count'] = functions.pagecount(aggregate['count'], limit)
	resp['total'] = aggregate['sum']
	resp['totalprice'] = aggregate['sumprice']

	qry = """SELECT
				p.id, uc.id AS user_cardid, c.name, cs.name AS setname, cs.code AS setcode,
				get_rarity(p.rarity) AS rarity, uc.quantity, uc.foil,
				get_price(uc.id) AS price,
				get_base_price(uc.id) AS base_price,
				COALESCE(
					(SELECT currencycode FROM app.enduser WHERE id = uc.userid),
					'USD'
				) AS currencycode,
				p.collectornumber, p.card_setid,
				CASE WHEN p.language != 'en' THEN UPPER(p.language) END AS language
			FROM user_card uc
			LEFT JOIN printing p ON (uc.printingid = p.id)
			LEFT JOIN card c ON (p.cardid = c.id)
			LEFT JOIN card_set cs ON (p.card_setid = cs.id)
			WHERE uc.userid = %s"""
	qargs = (session['userid'],)

	if filters['search']:
		qry += " AND c.name ILIKE %s"
		qargs += ('%' + filters['search'] + '%',)
	if filters['set']:
		qry += " AND p.card_setid = %s"
		qargs += (filters['set'],)
	if filters['rarity']:
		qry += " AND p.rarity = %s"
		qargs += (filters['rarity'],)

	qry += """ ORDER BY
				%s %s,
				cs.code,
				p.collectornumber
			LIMIT
				%%s
			OFFSET %%s
			""" % (sort, sort_desc)
	qargs += (limit, offset,)
	resp['cards'] = fetch_query(qry, qargs)
	for c in resp['cards']:
		c['imageurl'] = serve_static_file('images/card_image_{}.jpg'.format(c['id']))
		c['arturl'] = serve_static_file('images/card_art_{}.jpg'.format(c['id']))

		if c['currencycode'] == 'USD':
			c['base_price'] = None

		# Remove keys unnecessary in response
		del c['card_setid']

	return resp


def add(printingid: int, foil: bool, quantity: int) -> None:
	existing = fetch_query(
		"""
		SELECT id FROM user_card WHERE printingid = %s AND foil = %s AND userid = %s
		""",
		(printingid, foil, session['userid'],),
		single_row=True
	)
	if existing:
		mutate_query(
			"UPDATE user_card SET quantity = quantity + %s WHERE id = %s",
			(quantity, existing['id'],)
		)
	else:
		mutate_query(
			"""
			INSERT INTO user_card (
				printingid, userid, foil, quantity
			) SELECT %s, %s, %s, %s
			WHERE NOT EXISTS (
				SELECT 1 FROM user_card
				WHERE printingid = %s AND foil = %s AND userid = %s
			)
			""",
			(
				printingid,
				session['userid'],
				foil,
				quantity,
				printingid,
				foil,
				session['userid'],
			)
		)


def remove(printingid: int, foil: bool, quantity: int) -> None:
	existing = fetch_query(
		"""
		SELECT
			id, quantity FROM user_card
		WHERE printingid = %s
		AND foil = %s
		AND userid = %s
		AND quantity >= %s
		""",
		(printingid, foil, session['userid'], quantity,),
		single_row=True
	)
	if existing:
		if (existing['quantity'] - quantity) <= 0:
			qry = "DELETE FROM user_card WHERE id = %s"
			qargs = (existing['id'],)
		else:
			qry = "UPDATE user_card SET quantity = quantity - %s WHERE id = %s"
			qargs = (quantity, existing['id'],)
		mutate_query(qry, qargs)
	else:
		raise Exception('Could not find card {}.'.format(printingid))


def import_cards(cards: list) -> None:
	sets = []
	for c in cards:
		if c['set'] not in [x['code'] for x in sets]:
			sets.append({'code': c['set'], 'name': c['set_name']})

	for s in sets:
		# Check if already have a record of this set
		existing = fetch_query(
			"SELECT 1 FROM card_set WHERE LOWER(code) = LOWER(%s)",
			(s['code'],)
		)
		if not existing:
			resp = scryfall.get_set(s['code'])
			mutate_query(
				"""
				INSERT INTO card_set (
					name, code, released, tcgplayer_groupid
				) SELECT
					%s, %s, %s, %s
				WHERE NOT EXISTS (SELECT * FROM card_set WHERE code = %s)
				""",
				(
					resp['name'],
					s['code'],
					resp['released_at'],
					resp.get('tcgplayer_id'),
					s['code'],
				)
			)

	# more efficient than attempting inserts
	resp = fetch_query(
		"SELECT DISTINCT scryfallid FROM printing WHERE scryfallid IS NOT NULL"
	)
	scryfall_ids = [x['scryfallid'] for x in resp]

	new_cards = []
	for c in cards:
		if c['scryfallid'] in scryfall_ids:
			print('Existing {}...'.format(c['scryfallid']))
			continue

		existing = fetch_query(
			"SELECT id FROM card WHERE LOWER(name) = LOWER(%s)",
			(c['name'],),
			single_row=True
		)
		if existing:
			cardid = existing['id']
		else:
			print('Inserting card {}'.format(c['name']))
			new = mutate_query(
				"""
				INSERT INTO card (
					name, colors, multifaced, cmc, typeline, manacost
				) SELECT
					%s, %s, %s, %s, %s, %s
				WHERE NOT EXISTS (
					SELECT 1 FROM card WHERE LOWER(name) = LOWER(%s)
				) RETURNING id
				""",
				(
					c['name'], c['colors'], c['multifaced'], c['cmc'],
					strip_unicode_characters(c['typeline']), c['manacost'],
					c['name'],
				),
				returning=True
			)
			cardid = new['id']

		new = mutate_query(
			"""
			INSERT INTO printing (
				cardid, collectornumber, multiverseid, scryfallid,
				card_setid,
				rarity, language
			) SELECT
				%s, %s, %s, %s,
				(SELECT id FROM card_set WHERE code = %s),
				%s, %s
			WHERE NOT EXISTS (
				SELECT 1 FROM printing
				WHERE cardid = %s
				AND collectornumber = %s
				AND card_setid = (SELECT id FROM card_set WHERE code = %s)
			) RETURNING id
			""",
			(
				cardid, c['collectornumber'], c['multiverseid'], c['scryfallid'],
				c['set'],
				c['rarity'], c['language'],
				cardid, c['collectornumber'], c['set'],
			),
			returning=True
		)
		if new:
			print('Inserted printing {}'.format(c['name']))
			c['id'] = new['id']
			c['set_code'] = c['set']  # Key needed for searching on tcgplayer
			c['productid'] = tcgplayer.search(c)
			if c['productid'] is not None:
				mutate_query(
					"""
					UPDATE
						printing
					SET
						tcgplayer_productid = %s
					WHERE
						id = %s AND
						NOT is_basic_land(cardid)
					""",
					(c['productid'], c['id'],)
				)
				new_cards.append({'id': c['id'], 'productid': c['productid']})

	bulk_lots = ([new_cards[i:i + 250] for i in range(0, len(new_cards), 250)])
	prices = {}
	for lot in bulk_lots:
		prices.update(
			tcgplayer.get_price({
				str(c['id']): str(c['productid'])
				for c in lot
				if c['productid'] is not None
			})
		)

	updates = []
	for printingid, price in prices.items():
		updates.append({
			'price': price['normal'],
			'foilprice': price['foil'],
			'id': printingid
		})
	mutate_query(
		"""
		UPDATE
			printing
		SET
			price = %(price)s,
			foilprice = %(foilprice)s
		WHERE
			id = %(id)s
		""",
		updates,
		executemany=True
	)
