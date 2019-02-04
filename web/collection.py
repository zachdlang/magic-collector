# Third party imports
from flask import session

# Local imports
from web import scryfall
from sitetools.utility import (
	pagecount, fetch_query, mutate_query
)


def get(params):
	resp = {}

	limit = 50
	page = 1
	if params.get('page'):
		page = int(params.get('page'))
	offset = page * limit - limit

	# Sorting
	cols = {
		'name': 'c.name',
		'setname': 'cs.name',
		'rarity': 'c.rarity',
		'quantity': 'uc.quantity',
		'foil': 'uc.foil',
		'price': 'get_price(uc.id)'
	}
	sort = cols.get(params.get('sort'), 'c.name')
	descs = {'asc': 'ASC', 'desc': 'DESC'}
	sort_desc = descs.get(params.get('sort_desc'), 'ASC')

	# Filters
	filters = {
		'search': '%' + params['filter_search'] + '%' if params.get('filter_search') else None,
		'set': params.get('filter_set'),
		'rarity': params.get('filter_rarity')
	}

	qry = "SELECT count(*) AS count, sum(quantity) AS sum FROM user_card WHERE userid = %s"
	qargs = (session['userid'],)
	if filters['search']:
		qry += " AND (SELECT name FROM card WHERE id = cardid) ILIKE %s"
		qargs += (filters['search'],)
	if filters['set']:
		qry += " AND (SELECT card_setid FROM card WHERE id = cardid) = %s"
		qargs += (filters['set'],)
	if filters['rarity']:
		qry += " AND (SELECT rarity FROM card WHERE id = cardid) = %s"
		qargs += (filters['rarity'],)
	aggregate = fetch_query(qry, qargs, single_row=True)
	resp['count'] = pagecount(aggregate['count'], limit)
	resp['total'] = aggregate['sum']

	qry = """SELECT
				c.id, c.name, cs.name AS setname, cs.code,
				get_rarity(c.rarity) AS rarity, uc.quantity, uc.foil, get_price(uc.id) AS price,
				COALESCE((SELECT currencycode FROM app.enduser WHERE id = uc.userid), 'USD') AS currencycode,
				c.multiverseid, c.imageurl, c.arturl, cs.iconurl, c.card_setid
			FROM user_card uc
			LEFT JOIN card c ON (uc.cardid = c.id)
			LEFT JOIN card_set cs ON (c.card_setid = cs.id)
			WHERE uc.userid = %s"""
	qargs = (session['userid'],)

	if filters['search']:
		qry += " AND c.name ILIKE %s"
		qargs += ('%' + filters['search'] + '%',)
	if filters['set']:
		qry += " AND c.card_setid = %s"
		qargs += (filters['set'],)
	if filters['rarity']:
		qry += " AND c.rarity = %s"
		qargs += (filters['rarity'],)

	qry += " ORDER BY %s %s, cs.code, c.collectornumber LIMIT %%s OFFSET %%s" % (sort, sort_desc)
	qargs += (limit, offset,)
	resp['cards'] = fetch_query(qry, qargs)
	for c in resp['cards']:
		if c['imageurl'] is None or c['arturl'] is None:
			image_resp = scryfall.get(c['multiverseid'])
			c['imageurl'] = image_resp['imageurl']
			c['arturl'] = image_resp['arturl']
			mutate_query("UPDATE card SET imageurl = %s, arturl = %s WHERE id = %s", (c['imageurl'], c['arturl'], c['id'],))
		if c['iconurl'] is None:
			c['iconurl'] = scryfall.get_set(c['code'])['icon_svg_uri']
			mutate_query("UPDATE card_set SET iconurl = %s WHERE id = %s", (c['iconurl'], c['card_setid'],))

		# Remove keys unnecessary in response
		del c['id']
		del c['code']
		del c['multiverseid']
		del c['card_setid']

	return resp


def add(rows):
	for row in rows:
		foil = int(row['Foil quantity']) > 0
		qry = "SELECT id FROM user_card WHERE cardid = (SELECT id FROM card WHERE multiverseid = %s) AND foil = %s AND userid = %s"
		qargs = (row['MultiverseID'], foil, session['userid'],)
		existing = fetch_query(qry, qargs, single_row=True)
		if existing:
			qry = "UPDATE user_card SET quantity = quantity + %s WHERE id = %s"
			qargs = (row['Quantity'], existing['id'],)
		else:
			qry = """INSERT INTO user_card (cardid, userid, quantity, foil) SELECT id, %s, %s, %s FROM card WHERE multiverseid = %s
					AND NOT EXISTS (SELECT * FROM user_card WHERE cardid = card.id AND foil = %s AND userid = %s)"""
			qargs = (session['userid'], row['Quantity'], foil, row['MultiverseID'], foil, session['userid'],)
		mutate_query(qry, qargs)
