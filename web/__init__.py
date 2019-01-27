# Standard library imports
import os
import logging
from logging.handlers import SMTPHandler

# Third party imports
from flask import (
	request, session, g, jsonify, send_from_directory, flash, redirect, url_for,
	render_template
)
import psycopg2
import psycopg2.extras

# Local imports
from web import scryfall, tcgplayer, openexchangerates
from sitetools.utility import (
	BetterExceptionFlask, is_logged_in, params_to_dict, query_to_dict_list,
	login_required, pagecount, check_image_exists, check_login
)

app = BetterExceptionFlask(__name__)

app.config.from_pyfile('site_config.cfg')
app.secret_key = app.config['SECRETKEY']

app.jinja_env.globals.update(is_logged_in=is_logged_in)

if not app.debug:
	ADMINISTRATORS = [app.config['TO_EMAIL']]
	msg = 'Internal Error on collector'
	mail_handler = SMTPHandler('127.0.0.1', app.config['FROM_EMAIL'], ADMINISTRATORS, msg)
	mail_handler.setLevel(logging.CRITICAL)
	app.logger.addHandler(mail_handler)


@app.errorhandler(500)
def internal_error(e):
	return jsonify(error='Internal error occurred. Please try again later.'), 500


@app.before_request
def before_request():
	if '/static/' in request.path:
		return
	g.conn = psycopg2.connect(
		database=app.config['DBNAME'], user=app.config['DBUSER'],
		password=app.config['DBPASS'], port=app.config['DBPORT'],
		host=app.config['DBHOST'],
		cursor_factory=psycopg2.extras.DictCursor,
		application_name=request.path
	)
	g.config = app.config


@app.route('/favicon.ico')
@app.route('/robots.txt')
@app.route('/sitemap.xml')
def static_from_root():
	return send_from_directory(app.static_folder, request.path[1:])


@app.route('/login', methods=['GET', 'POST'])
def login():
	if is_logged_in():
		return redirect(url_for('home'))

	if request.method == 'POST':
		params = params_to_dict(request.form)

		ok = check_login(params.get('username'), params.get('password'))

		if ok:
			return redirect(url_for('home'))
		else:
			flash('Login failed.', 'danger')
			return redirect(url_for('login'))

	return render_template('login.html')


@app.route('/logout', methods=['GET'])
def logout():
	session.pop('userid', None)
	return redirect(url_for('login'))


@app.route('/', methods=['GET'])
@login_required
def home():
	return render_template('collector.html')


@app.route('/get_sets', methods=['GET'])
@login_required
def get_sets():
	cursor = g.conn.cursor()
	cursor.execute("""SELECT id, name, iconurl FROM card_set ORDER BY released DESC""")
	sets = query_to_dict_list(cursor)
	cursor.close()

	return jsonify(sets=sets)


@app.route('/get_collection', methods=['GET'])
@login_required
def get_collection():
	params = params_to_dict(request.args)
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
		'set': params.get('filter_set')
	}

	cursor = g.conn.cursor()

	qry = """SELECT count(*) FROM user_card WHERE userid = %s"""
	qargs = (session['userid'],)
	if filters['search']:
		qry += """ AND (SELECT name FROM card WHERE id = cardid) ILIKE %s"""
		qargs += (filters['search'],)
	if filters['set']:
		qry += """ AND (SELECT card_setid FROM card WHERE id = cardid) = %s"""
		qargs += (filters['set'],)
	cursor.execute(qry, qargs)
	count = pagecount(cursor.fetchone()[0], limit)

	qry = """SELECT
				c.id, c.name, cs.name AS setname, cs.code,
				get_rarity(c.rarity) AS rarity, uc.quantity, uc.foil, get_price(uc.id) AS price,
				COALESCE((SELECT currencycode FROM app.enduser WHERE id = uc.userid), 'USD') AS currencycode,
				c.multiverseid, c.imageurl, cs.iconurl, c.card_setid
			FROM user_card uc
			LEFT JOIN card c ON (uc.cardid = c.id)
			LEFT JOIN card_set cs ON (c.card_setid = cs.id)
			WHERE uc.userid = %s"""
	qargs = (session['userid'],)

	if filters['search']:
		qry += """ AND c.name ILIKE %s"""
		qargs += ('%' + filters['search'] + '%',)
	if filters['set']:
		qry += """ AND c.card_setid = %s"""
		qargs += (filters['set'],)

	qry += """ ORDER BY %s %s, cs.code, c.collectornumber LIMIT %%s OFFSET %%s""" % (sort, sort_desc)
	qargs += (limit, offset,)
	cursor.execute(qry, qargs)
	cards = query_to_dict_list(cursor)
	for c in cards:
		if c['imageurl'] is None:
			c['imageurl'] = scryfall.get(c['multiverseid'])['imageurl']
			cursor.execute("""UPDATE card SET imageurl = %s WHERE id = %s""", (c['imageurl'], c['id'],))
			g.conn.commit()
		if c['iconurl'] is None:
			c['iconurl'] = scryfall.get_set(c['code'])['icon_svg_uri']
			cursor.execute("""UPDATE card_set SET iconurl = %s WHERE id = %s""", (c['iconurl'], c['card_setid'],))
			g.conn.commit()

		# Remove keys unnecessary in response
		del c['id']
		del c['code']
		del c['multiverseid']
		del c['card_setid']

	cursor.close()
	return jsonify(cards=cards, count=count)


@app.route('/search', methods=['GET'])
@login_required
def search():
	params = params_to_dict(request.args)
	results = []

	if params.get('query'):
		search = '%' + params['query'] + '%'
		cursor = g.conn.cursor()
		qry = """SELECT c.id, c.name, s.code, s.name AS setname, s.iconurl FROM card c LEFT JOIN card_set s ON (c.card_setid=s.id) WHERE c.name ILIKE %s ORDER BY name ASC LIMIT 50"""
		cursor.execute(qry, (search,))
		results = query_to_dict_list(cursor)
		for r in results:
			if r['iconurl'] is None:
				r['iconurl'] = scryfall.get_set(r['code'])['icon_svg_uri']
				cursor.execute("""UPDATE card_set SET iconurl = %s WHERE id = %s""", (r['iconurl'], r['card_setid'],))
				g.conn.commit()

		cursor.close()

	return jsonify(results=results)


@app.route('/csv_upload', methods=['POST'])
@login_required
def csv_upload():
	import csv

	filename = '/tmp/upload_%s.csv' % session['userid']
	request.files['upload'].save(filename)
	rows = []
	multiverse_ids = []
	with open(filename) as csvfile:
		importreader = csv.DictReader(csvfile)
		for row in importreader:
			rows.append(row)
			multiverse_ids.append(int(row['MultiverseID']))
	os.remove(filename)

	new = []
	cursor = g.conn.cursor()
	for multiverseid in multiverse_ids:
		cursor.execute("""SELECT * FROM card WHERE multiverseid = %s""", (multiverseid,))
		if cursor.rowcount == 0:
			new.append(multiverseid)
	cursor.close()

	bulk_lots = ([new[i:i + 75] for i in range(0, len(new), 75)])
	for lot in bulk_lots:
		resp = scryfall.get_bulk(lot)
		import_cards(resp)

	cursor = g.conn.cursor()
	for row in rows:
		foil = int(row['Foil quantity']) > 0
		qry = """SELECT id FROM user_card WHERE cardid = (SELECT id FROM card WHERE multiverseid = %s) AND foil = %s AND userid = %s"""
		qargs = (row['MultiverseID'], foil, session['userid'],)
		cursor.execute(qry, qargs)
		if cursor.rowcount > 0:
			user_cardid = cursor.fetchone()[0]
			qry = """UPDATE user_card SET quantity = quantity + %s WHERE id = %s"""
			qargs = (row['Quantity'], user_cardid,)
		else:
			qry = """INSERT INTO user_card (cardid, userid, quantity, foil) SELECT id, %s, %s, %s FROM card WHERE multiverseid = %s
					AND NOT EXISTS (SELECT * FROM user_card WHERE cardid = card.id AND foil = %s AND userid = %s)"""
			qargs = (session['userid'], row['Quantity'], foil, row['MultiverseID'], foil, session['userid'],)
		cursor.execute(qry, qargs)
		g.conn.commit()
	cursor.close()

	return jsonify(new)


def import_cards(cards):
	cursor = g.conn.cursor()
	sets = []
	for c in cards:
		if c['set'] not in [x['code'] for x in sets]:
			sets.append({'code': c['set'], 'name': c['set_name']})

	for s in sets:
		# Check if already have a record of this set
		cursor.execute("""SELECT 1 FROM card_set WHERE code = %s""", (s['code'],))
		if cursor.rowcount == 0:
			resp = scryfall.get_set(s['code'])
			qry = """INSERT INTO card_set (name, code, released, tcgplayer_groupid) SELECT %s, %s
					WHERE NOT EXISTS (SELECT * FROM card_set WHERE code = %s)"""
			qargs = (resp['name'], s['code'], resp['released_at'], resp.get('tcgplayer_id'), s['code'],)
			cursor.execute(qry, qargs)
			g.conn.commit()

	# more efficient than attempting inserts
	cursor.execute("""SELECT multiverseid FROM card""")
	multiverse_ids = [x['multiverseid'] for x in query_to_dict_list(cursor)]

	new_cards = []
	for c in cards:
		if c['multiverseid'] in multiverse_ids:
			print('Existing %s...' % c['multiverseid'])
			continue
		qry = """INSERT INTO card (
				collectornumber, multiverseid, name, card_setid, colors,
				rarity, multifaced) SELECT
				%s, %s, %s, (SELECT id FROM card_set WHERE code = %s), %s,
				%s, %s
				WHERE NOT EXISTS (SELECT * FROM card WHERE multiverseid = %s)
				RETURNING id"""
		qargs = (
			c['collectornumber'], c['multiverseid'], c['name'], c['set'], c['colors'],
			c['rarity'], c['multifaced'],
			c['multiverseid'],
		)
		cursor.execute(qry, qargs)
		if cursor.rowcount > 0:
			c['id'] = cursor.fetchone()[0]
			c['productid'] = tcgplayer.search(c)
			if c['productid'] is not None:
				cursor.execute("""UPDATE card SET tcgplayer_productid = %s WHERE id = %s""", (c['productid'], c['id'],))
				new_cards.append({'id': c['id'], 'productid': c['productid']})
		g.conn.commit()

	bulk_lots = ([new_cards[i:i + 250] for i in range(0, len(new_cards), 250)])
	prices = {}
	for lot in bulk_lots:
		prices.update(tcgplayer.get_price({str(c['id']): str(c['productid']) for c in lot if c['productid'] is not None}))

	updates = []
	for cardid, price in prices.items():
		updates.append({'price': price['normal'], 'foilprice': price['foil'], 'id': cardid})
	cursor.executemany("""UPDATE card SET price = %(price)s, foilprice = %(foilprice)s WHERE id = %(id)s""", updates)
	g.conn.commit()
	cursor.close()


@app.route('/update_prices', methods=['GET'])
def update_prices():
	cursor = g.conn.cursor()
	qry = """SELECT c.id, c.collectornumber, c.name, c.rarity,
				s.name AS set_name, s.tcgplayer_groupid AS groupid,
				c.tcgplayer_productid AS productid
			FROM card c
			LEFT JOIN card_set s ON (s.id = c.card_setid)
			WHERE EXISTS(SELECT 1 FROM user_card WHERE cardid=c.id)
			ORDER BY c.name ASC"""
	cursor.execute(qry)
	cards = query_to_dict_list(cursor)
	for c in cards:
		if c['productid'] is None:
			c['productid'] = tcgplayer.search(c)
			if c['productid'] is not None:
				cursor.execute("""UPDATE card SET tcgplayer_productid = %s WHERE id = %s""", (c['productid'], c['id'],))
				g.conn.commit()

	# Filter out cards without tcgplayerid to save requests
	cards = [c for c in cards if c['productid'] is not None]
	bulk_lots = ([cards[i:i + 250] for i in range(0, len(cards), 250)])
	prices = {}
	for lot in bulk_lots:
		prices.update(tcgplayer.get_price({str(c['id']): str(c['productid']) for c in lot if c['productid'] is not None}))

	updates = []
	for cardid, price in prices.items():
		updates.append({'price': price['normal'], 'foilprice': price['foil'], 'id': cardid})
	cursor.executemany("""UPDATE card SET price = %(price)s, foilprice = %(foilprice)s WHERE id = %(id)s""", updates)
	g.conn.commit()
	cursor.close()
	return jsonify()


@app.route('/update_rates', methods=['POST'])
def update_rates():
	rates = openexchangerates.get()
	cursor = g.conn.cursor()
	for code, rate in rates.items():
		cursor.execute("""SELECT update_rates(%s, %s)""", (code, rate,))
	g.conn.commit()
	cursor.close()
	return jsonify()


@app.route('/check_images', methods=['GET'])
def check_images():
	cursor = g.conn.cursor()
	cursor.execute("""SELECT id, name, code, iconurl FROM card_set ORDER BY name ASC""")
	sets = query_to_dict_list(cursor)

	for s in sets:
		if s['iconurl'] is not None:
			# Check for bad icon URLs
			if check_image_exists(s['iconurl']) is False:
				print('Set icon URL could not be found for %s.' % s['name'])
				cursor.execute("""UPDATE card_set SET iconurl = NULL WHERE id = %s""", (s['id'],))
				g.conn.commit()
				# Null out local copy for refreshing image below
				s['iconurl'] = None

		if s['iconurl'] is None:
			# Fetch icon URLs for anything without one
			s['iconurl'] = scryfall.get_set(s['code'])['icon_svg_uri']
			if s['iconurl'] is not None:
				print('Found new set icon URL for %s.' % s['name'])
				cursor.execute("""UPDATE card_set SET iconurl = %s WHERE id = %s""", (s['iconurl'], s['id'],))
				g.conn.commit()

	qry = """SELECT id, name, multiverseid, imageurl
			FROM card
			WHERE EXISTS(SELECT 1 FROM user_card WHERE cardid=card.id)
			ORDER BY name ASC"""
	cursor.execute(qry)
	cards = query_to_dict_list(cursor)

	for c in cards:
		if c['imageurl'] is not None:
			# Check for bad image URLs
			if check_image_exists(c['imageurl']) is False:
				print('Card image URL for could not be found for %s.' % c['name'])
				cursor.execute("""UPDATE card SET imageurl = NULL WHERE id = %s""", (c['id'],))
				g.conn.commit()
				# Null out local copy for refreshing image below
				c['imageurl'] = None

		if c['imageurl'] is None:
			# Fetch image URLs for anything without one
			c['imageurl'] = scryfall.get(c['multiverseid'])['imageurl']
			if c['imageurl'] is not None:
				print('Found new card image URL for %s.' % c['name'])
				cursor.execute("""UPDATE card SET imageurl = %s WHERE id = %s""", (c['imageurl'], c['id'],))
				g.conn.commit()

	cursor.close()
	return jsonify()


if __name__ == '__main__':
	app.run()
