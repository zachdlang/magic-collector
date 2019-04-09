# Third party imports
from flask import session, url_for

# Local imports
from sitetools.utility import (
	pagecount, fetch_query, mutate_query
)


def get(params):
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

	qry = """SELECT count(*) AS count,
				sum(quantity) AS sum,
				sum(quantity * get_price(id)) AS sumprice
			FROM user_card
			WHERE userid = %s"""
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
	resp['totalprice'] = aggregate['sumprice']

	qry = """SELECT
				c.id, uc.id AS user_cardid, c.name, cs.name AS setname, cs.code AS setcode,
				get_rarity(c.rarity) AS rarity, uc.quantity, uc.foil, get_price(uc.id) AS price,
				COALESCE((SELECT currencycode FROM app.enduser WHERE id = uc.userid), 'USD') AS currencycode,
				c.collectornumber, c.card_setid
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
		c['imageurl'] = url_for('static', filename='images/card_image_{}.jpg'.format(c['id']))
		c['arturl'] = url_for('static', filename='images/card_art_{}.jpg'.format(c['id']))

		# Remove keys unnecessary in response
		del c['card_setid']

	return resp


def add(cardid, foil, quantity):
	qry = "SELECT id FROM user_card WHERE cardid = %s AND foil = %s AND userid = %s"
	qargs = (cardid, foil, session['userid'],)
	existing = fetch_query(qry, qargs, single_row=True)
	if existing:
		qry = "UPDATE user_card SET quantity = quantity + %s WHERE id = %s"
		qargs = (quantity, existing['id'],)
	else:
		qry = """INSERT INTO user_card (cardid, userid, foil, quantity) SELECT %s, %s, %s, %s
				WHERE NOT EXISTS (SELECT 1 FROM user_card WHERE cardid = %s AND foil = %s AND userid = %s)"""
		qargs = (cardid, session['userid'], foil, quantity, cardid, foil, session['userid'],)
	mutate_query(qry, qargs)


def remove(cardid, foil, quantity):
	qry = "SELECT id, quantity FROM user_card WHERE cardid = %s AND foil = %s AND userid = %s AND quantity >= %s"
	qargs = (cardid, foil, session['userid'], quantity,)
	existing = fetch_query(qry, qargs, single_row=True)
	if existing:
		if (existing['quantity'] - quantity) <= 0:
			qry = "DELETE FROM user_card WHERE id = %s"
			qargs = (existing['id'],)
		else:
			qry = "UPDATE user_card SET quantity = quantity - %s WHERE id = %s"
			qargs = (quantity, existing['id'],)
		mutate_query(qry, qargs)
	else:
		raise Exception('Could not find card %s.' % cardid)
