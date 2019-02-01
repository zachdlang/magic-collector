# Standard library imports
import os
import logging
from logging.handlers import SMTPHandler

# Third party imports
from flask import (
	request, session, jsonify, send_from_directory, flash, redirect, url_for,
	render_template
)

# Local imports
from web import collection, deck, scryfall, tcgplayer, openexchangerates
from sitetools.utility import (
	BetterExceptionFlask, is_logged_in, params_to_dict,
	login_required, check_image_exists, check_login, fetch_query,
	mutate_query, disconnect_database, handle_exception
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
	return handle_exception


@app.teardown_appcontext
def teardown(error):
	disconnect_database()


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
	return render_template('collection.html', active='collection')


@app.route('/get_sets', methods=['GET'])
@login_required
def get_sets():
	sets = fetch_query("SELECT id, name, iconurl FROM card_set ORDER BY released DESC")

	return jsonify(sets=sets)


@app.route('/get_collection', methods=['GET'])
@login_required
def get_collection():
	params = params_to_dict(request.args)
	resp = collection.get(params)

	return jsonify(**resp)


@app.route('/search', methods=['GET'])
@login_required
def search():
	params = params_to_dict(request.args)
	results = []

	if params.get('query'):
		search = '%' + params['query'] + '%'
		qry = """SELECT c.id, c.name, s.code, s.name AS setname, s.iconurl
				FROM card c
				LEFT JOIN card_set s ON (c.card_setid=s.id)
				WHERE c.name ILIKE %s
				ORDER BY name ASC LIMIT 50"""
		results = fetch_query(qry, (search,))
		for r in results:
			if r['iconurl'] is None:
				r['iconurl'] = scryfall.get_set(r['code'])['icon_svg_uri']
				mutate_query("UPDATE card_set SET iconurl = %s WHERE id = %s", (r['iconurl'], r['card_setid'],))

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
	for multiverseid in multiverse_ids:
		qry = "SELECT * FROM card WHERE multiverseid = %s"
		qargs = (multiverseid,)
		if len(fetch_query(qry, qargs)) == 0:
			new.append(multiverseid)

	bulk_lots = ([new[i:i + 75] for i in range(0, len(new), 75)])
	for lot in bulk_lots:
		resp = scryfall.get_bulk(lot)
		import_cards(resp)

	collection.add(rows)

	return jsonify(new)


def import_cards(cards):
	sets = []
	for c in cards:
		if c['set'] not in [x['code'] for x in sets]:
			sets.append({'code': c['set'], 'name': c['set_name']})

	for s in sets:
		# Check if already have a record of this set
		existing = fetch_query("SELECT 1 FROM card_set WHERE LOWER(code) = LOWER(%s)", (s['code'],))
		if not existing:
			resp = scryfall.get_set(s['code'])
			qry = """INSERT INTO card_set (name, code, released, tcgplayer_groupid) SELECT %s, %s, %s, %s
					WHERE NOT EXISTS (SELECT * FROM card_set WHERE code = %s)"""
			qargs = (resp['name'], s['code'], resp['released_at'], resp.get('tcgplayer_id'), s['code'],)
			mutate_query(qry, qargs)

	# more efficient than attempting inserts
	multiverse_ids = [x['multiverseid'] for x in fetch_query("SELECT multiverseid FROM card")]

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
		new = mutate_query(qry, qargs)
		if new:
			c['id'] = new['id']
			c['productid'] = tcgplayer.search(c)
			if c['productid'] is not None:
				mutate_query("UPDATE card SET tcgplayer_productid = %s WHERE id = %s", (c['productid'], c['id'],))
				new_cards.append({'id': c['id'], 'productid': c['productid']})

	bulk_lots = ([new_cards[i:i + 250] for i in range(0, len(new_cards), 250)])
	prices = {}
	for lot in bulk_lots:
		prices.update(tcgplayer.get_price({str(c['id']): str(c['productid']) for c in lot if c['productid'] is not None}))

	updates = []
	for cardid, price in prices.items():
		updates.append({'price': price['normal'], 'foilprice': price['foil'], 'id': cardid})
	mutate_query("UPDATE card SET price = %(price)s, foilprice = %(foilprice)s WHERE id = %(id)s", updates, executemany=True)


@app.route('/update_prices', methods=['GET'])
def update_prices():
	qry = """SELECT c.id, c.collectornumber, c.name, c.rarity,
				s.name AS set_name, s.tcgplayer_groupid AS groupid,
				c.tcgplayer_productid AS productid
			FROM card c
			LEFT JOIN card_set s ON (s.id = c.card_setid)
			WHERE EXISTS(SELECT 1 FROM user_card WHERE cardid=c.id)
			ORDER BY c.name ASC"""
	cards = fetch_query(qry)
	for c in cards:
		if c['productid'] is None:
			c['productid'] = tcgplayer.search(c)
			if c['productid'] is not None:
				mutate_query("UPDATE card SET tcgplayer_productid = %s WHERE id = %s", (c['productid'], c['id'],))

	# Filter out cards without tcgplayerid to save requests
	cards = [c for c in cards if c['productid'] is not None]
	bulk_lots = ([cards[i:i + 250] for i in range(0, len(cards), 250)])
	prices = {}
	for lot in bulk_lots:
		prices.update(tcgplayer.get_price({str(c['id']): str(c['productid']) for c in lot if c['productid'] is not None}))

	updates = []
	for cardid, price in prices.items():
		updates.append({'price': price['normal'], 'foilprice': price['foil'], 'id': cardid})
	mutate_query("UPDATE card SET price = %(price)s, foilprice = %(foilprice)s WHERE id = %(id)s", updates, executemany=True)
	return jsonify()


@app.route('/update_rates', methods=['POST'])
def update_rates():
	rates = openexchangerates.get()
	updates = [{'code': code, 'rate': rate} for code, rate in rates.items()]
	mutate_query("SELECT update_rates(%(code)s, %(rate)s)", updates, executemany=True)
	return jsonify()


@app.route('/check_images', methods=['GET'])
def check_images():
	sets = fetch_query("SELECT id, name, code, iconurl FROM card_set ORDER BY name ASC")

	for s in sets:
		if s['iconurl'] is not None:
			# Check for bad icon URLs
			if check_image_exists(s['iconurl']) is False:
				print('Set icon URL could not be found for %s.' % s['name'])
				mutate_query("""UPDATE card_set SET iconurl = NULL WHERE id = %s""", (s['id'],))
				# Null out local copy for refreshing image below
				s['iconurl'] = None

		if s['iconurl'] is None:
			# Fetch icon URLs for anything without one
			s['iconurl'] = scryfall.get_set(s['code'])['icon_svg_uri']
			if s['iconurl'] is not None:
				print('Found new set icon URL for %s.' % s['name'])
				mutate_query("""UPDATE card_set SET iconurl = %s WHERE id = %s""", (s['iconurl'], s['id'],))

	qry = """SELECT id, name, multiverseid, imageurl
			FROM card
			WHERE EXISTS(SELECT 1 FROM user_card WHERE cardid=card.id)
			ORDER BY name ASC"""
	cards = fetch_query(qry)

	for c in cards:
		if c['imageurl'] is not None:
			# Check for bad image URLs
			if check_image_exists(c['imageurl']) is False:
				print('Card image URL for could not be found for %s.' % c['name'])
				mutate_query("""UPDATE card SET imageurl = NULL WHERE id = %s""", (c['id'],))
				# Null out local copy for refreshing image below
				c['imageurl'] = None

		if c['imageurl'] is None:
			# Fetch image URLs for anything without one
			c['imageurl'] = scryfall.get(c['multiverseid'])['imageurl']
			if c['imageurl'] is not None:
				print('Found new card image URL for %s.' % c['name'])
				mutate_query("""UPDATE card SET imageurl = %s WHERE id = %s""", (c['imageurl'], c['id'],))

	return jsonify()


@app.route('/decks', methods=['GET'])
@login_required
def decks():
	return render_template('decks.html', active='decks')


@app.route('/get_decks', methods=['GET'])
@login_required
def get_decks():
	decks = deck.get_all()
	return jsonify(decks=decks)


if __name__ == '__main__':
	app.run()
