# Standard library imports
import os

# Third party imports
from flask import (
	request, session, jsonify, send_from_directory, flash, redirect, url_for,
	render_template, Flask
)
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

# Local imports
from web import (
	collection, deck, scryfall, tcgplayer, config,
	functions
)
from sitetools.utility import (
	is_logged_in, params_to_dict,
	login_required, check_login, fetch_query,
	mutate_query, disconnect_database, handle_exception,
	check_celery_running
)

sentry_sdk.init(
	dsn=config.SENTRY_DSN,
	integrations=[FlaskIntegration()]
)

sentry_sdk.init(
	dsn=config.CELERY_SENTRY_DSN,
	integrations=[CeleryIntegration()]
)

app = Flask(__name__)

app.secret_key = config.SECRETKEY

app.jinja_env.globals.update(is_logged_in=is_logged_in)

# Import below app initialisation
from web import asynchro


@app.errorhandler(500)
def internal_error(e):
	return handle_exception()


@app.teardown_appcontext
def teardown(error):
	disconnect_database()


@app.route('/favicon.ico')
@app.route('/robots.txt')
@app.route('/sitemap.xml')
@app.route('/search.xml')
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
	params = params_to_dict(request.args)
	return render_template('collection.html', active='collection', search=params.get('search', ''))


@app.route('/get_sets', methods=['GET'])
@login_required
def get_sets():
	sets = fetch_query("SELECT id, name, code FROM card_set ORDER BY released DESC")
	for s in sets:
		if not os.path.exists(asynchro.set_icon_filename(s['code'])):
			asynchro.get_set_icon.delay(s['code'])
		s['iconurl'] = url_for('static', filename='images/set_icon_{}.svg'.format(s['code']))

	return jsonify(sets=sets)


@app.route('/get_collection', methods=['GET'])
@login_required
def get_collection():
	params = params_to_dict(request.args)
	resp = collection.get(params)
	for c in resp['cards']:
		if not os.path.exists(asynchro.card_art_filename(c['id'])):
			asynchro.get_card_art.delay(c['id'], c['setcode'], c['collectornumber'])
		if not os.path.exists(asynchro.card_image_filename(c['id'])):
			asynchro.get_card_image.delay(c['id'], c['setcode'], c['collectornumber'])
		del c['id']
		del c['collectornumber']

	return jsonify(**resp)


@app.route('/collection/card', methods=['GET'])
@login_required
def collection_card():
	params = params_to_dict(request.args)
	resp = {'card': None}

	if params.get('user_cardid'):
		resp['card'] = fetch_query(
			"""
			SELECT
				p.id, c.name, cs.name AS setname, get_rarity(p.rarity) AS rarity,
				uc.quantity, uc.foil, get_price(uc.id) AS price, p.tcgplayer_productid,
				COALESCE((SELECT currencycode FROM app.enduser WHERE id = uc.userid), 'USD') AS currencycode,
				total_printings_owned(uc.userid, p.cardid) AS printingsowned,
				(SELECT to_char(MAX(created), 'DD/MM/YY') FROM price_history WHERE printingid = p.id) AS price_lastupdated
			FROM user_card uc
			LEFT JOIN printing p ON (uc.printingid = p.id)
			LEFT JOIN card c ON (p.cardid = c.id)
			LEFT JOIN card_set cs ON (p.card_setid = cs.id)
			WHERE uc.userid = %s
			AND uc.id = %s
			""",
			(session['userid'], params['user_cardid'],),
			single_row=True
		)

	if resp['card']:
		resp['card']['arturl'] = url_for('static', filename='images/card_art_{}.jpg'.format(resp['card']['id']))
		resp['card']['decks'] = fetch_query(
			"""
			SELECT
				d.name, get_format(d.formatid) AS formatname,
				SUM(dc.quantity) AS quantity,
				d.cardartid
			FROM deck_card dc
			LEFT JOIN deck d ON (d.id = dc.deckid)
			WHERE d.deleted = false
			AND d.userid = %s
			AND dc.cardid IN (SELECT cardid FROM printing WHERE id = %s)
			GROUP BY d.id
			ORDER BY d.formatid, d.name
			""",
			(session['userid'], resp['card']['id'],)
		)
		for d in resp['card']['decks']:
			d['arturl'] = url_for('static', filename='images/card_art_{}.jpg'.format(d['cardartid']))
	else:
		resp['error'] = 'No card selected.'

	return jsonify(**resp)


@app.route('/collection/card/pricerefresh', methods=['GET'])
@login_required
def collection_card_pricerefresh():
	params = params_to_dict(request.args)

	printingid = None
	if params.get('user_cardid'):
		printingid = fetch_query(
			"SELECT printingid FROM user_card WHERE id = %s",
			(params['user_cardid'],),
			single_row=True
		)['printingid']

	if printingid is not None:
		return update_prices(printingid=printingid)

	return jsonify(error='No card found.')


@app.route('/collection/card/pricehistory', methods=['GET'])
@login_required
def collection_card_pricehistory():
	params = params_to_dict(request.args)
	resp = {}

	printingid = None
	if params.get('user_cardid'):
		printingid = fetch_query(
			"SELECT printingid FROM user_card WHERE id = %s",
			(params['user_cardid'],),
			single_row=True
		)['printingid']

	if printingid is not None:
		history = fetch_query(
			"""
			SELECT
				convert_price(ph.price, %s)::NUMERIC AS price,
				convert_price(ph.foilprice, %s)::NUMERIC AS foilprice,
				to_char(d.day, 'DD/MM/YY') AS created
			FROM generate_series(
				(SELECT MIN(created) FROM price_history WHERE printingid = %s),
				(SELECT MAX(created) FROM price_history WHERE printingid = %s),
				'1 day'::INTERVAL
			) d(day)
			LEFT JOIN price_history ph ON (ph.created = d.day AND ph.printingid = %s)
			""",
			(session['userid'], session['userid'], printingid, printingid, printingid,)
		)

		resp['dates'] = [h['created'] for h in history]
		prices = {
			'label': 'Price',
			'backgroundColor': 'rgba(40, 181, 246, 0.2)',
			'borderColor': 'rgba(40, 181, 246, 1)',
			'data': [functions.make_float(h['price']) for h in history]
		}
		foilprices = {
			'label': 'Foil Price',
			'backgroundColor': 'rgba(175, 90, 144, 0.2)',
			'borderColor': 'rgba(175, 90, 144, 1)',
			'data': [functions.make_float(h['foilprice']) for h in history]
		}

		resp['datasets'] = []
		if len(prices['data']) > 0:
			resp['datasets'].append(prices)
		if len(foilprices['data']) > 0:
			resp['datasets'].append(foilprices)
	else:
		resp['error'] = 'No card selected.'

	return jsonify(**resp)


@app.route('/collection/card/add', methods=['POST'])
@login_required
def collection_card_add():
	params = params_to_dict(request.form, bool_keys=['foil'])
	resp = {}

	if params.get('printingid'):
		collection.add(params['printingid'], params['foil'], params['quantity'])
	else:
		resp['error'] = 'No card selected.'

	return jsonify(**resp)


@app.route('/collection/card/edit', methods=['POST'])
@login_required
def collection_card_edit():
	params = params_to_dict(request.form, bool_keys=['foil'])

	update_current = True
	existing = fetch_query(
		"SELECT printingid, foil FROM user_card WHERE id = %s AND userid = %s",
		(params['user_cardid'], session['userid'],),
		single_row=True
	)
	if params.get('tcgplayer_productid'):
		print('Updating TCGplayer ID')
		mutate_query(
			"""
			UPDATE printing SET tcgplayer_productid = %s
			WHERE id = %s
			AND tcgplayer_productid IS NULL
			""",
			(params['tcgplayer_productid'], existing['printingid'],)
		)
	if existing['foil'] != params['foil']:
		# Foil has changed, need to check for opposite record
		opposite = fetch_query(
			"SELECT * FROM user_card WHERE printingid = %s AND userid = %s AND foil != %s",
			(existing['printingid'], session['userid'], existing['foil'],),
			single_row=True
		)
		if opposite:
			# There's an opposite record, update this instead
			mutate_query(
				"UPDATE user_card SET quantity = quantity + %s WHERE id = %s",
				(params['quantity'], opposite['id'],)
			)
			mutate_query("DELETE FROM user_card WHERE id = %s", (params['user_cardid'],))
			update_current = False

	if (update_current):
		if int(params['quantity']) > 0:
			mutate_query(
				"UPDATE user_card SET quantity = %s, foil = %s WHERE id = %s AND userid = %s",
				(params['quantity'], params['foil'], params['user_cardid'], session['userid'],)
			)
		else:
			mutate_query(
				"DELETE FROM user_card WHERE id = %s AND userid = %s",
				(params['user_cardid'], session['userid'],)
			)

	return jsonify()


@app.route('/search', methods=['GET'])
@login_required
def search():
	params = params_to_dict(request.args)
	results = []

	if params.get('query'):
		search = '%' + params['query'] + '%'
		qry = """SELECT p.id, c.name, s.code, s.name AS setname
				FROM printing p
				LEFT JOIN card c ON (p.cardid = c.id)
				LEFT JOIN card_set s ON (p.card_setid = s.id)
				WHERE c.name ILIKE %s
				ORDER BY c.name ASC, s.released DESC LIMIT 50"""
		results = fetch_query(qry, (search,))
		for r in results:
			if not os.path.exists(asynchro.set_icon_filename(r['code'])):
				asynchro.get_set_icon.delay(r['code'])
			r['iconurl'] = url_for('static', filename='images/set_icon_{}.svg'.format(r['code']))

	return jsonify(results=results)


@app.route('/csv_upload', methods=['POST'])
@login_required
def csv_upload():
	import csv

	upload = request.files['upload']
	filename = '/tmp/upload_%s_%s.csv' % (os.urandom(32), session['userid'])
	upload.save(filename)
	rows = []
	multiverse_ids = []
	with open(filename) as csvfile:
		importreader = csv.DictReader(csvfile)
		for row in importreader:
			rows.append({
				'multiverseid': row['MultiverseID'],
				'foil': int(row['Foil quantity']) > 0,
				'quantity': row['Quantity']
			})
			multiverse_ids.append(int(row['MultiverseID']))
	os.remove(filename)

	new = []
	for multiverseid in multiverse_ids:
		qry = "SELECT 1 FROM printing WHERE multiverseid = %s::TEXT"
		qargs = (multiverseid,)
		if len(fetch_query(qry, qargs)) == 0:
			new.append(multiverseid)

	bulk_lots = ([new[i:i + 75] for i in range(0, len(new), 75)])
	for lot in bulk_lots:
		resp = scryfall.get_bulk(lot)
		collection.import_cards(resp)

	importid = mutate_query(
		"""
		INSERT INTO import (filename, userid)
		VALUES (%s, %s)
		RETURNING id
		""",
		(upload.filename, session['userid'],),
		returning=True
	)['id']

	for row in rows:
		row['printingid'] = fetch_query(
			"SELECT id FROM printing WHERE multiverseid = %s::TEXT",
			(row['multiverseid'],),
			single_row=True
		)['id']
		# Doing this in loop instead of executemany due to needing RETURNING
		row['import_rowid'] = mutate_query(
			"""
			INSERT INTO import_row (importid, printingid, foil, quantity)
			VALUES (%s, %s, %s, %s)
			RETURNING id
			""",
			(importid, row['printingid'], row['foil'], row['quantity'],),
			returning=True
		)['id']

	complete_import(importid)

	return jsonify(new)


def complete_import(importid):
	rows = fetch_query(
		"SELECT * FROM import_row WHERE NOT complete AND importid = %s",
		(importid,)
	)
	for row in rows:
		collection.add(row['printingid'], row['foil'], row['quantity'])
		# Mark import for this card as completed
		mutate_query(
			"UPDATE import_row SET complete = true WHERE id = %s",
			(row['id'],)
		)


@app.route('/update_prices', methods=['GET'])
@app.route('/update_prices/<int:printingid>', methods=['GET'])
@check_celery_running
def update_prices(printingid=None):
	qry = """SELECT p.id, p.collectornumber, c.name, p.rarity,
				s.code AS set_code, s.name AS set_name, s.tcgplayer_groupid AS groupid,
				p.tcgplayer_productid AS productid
			FROM printing p
			LEFT JOIN card_set s ON (s.id = p.card_setid)
			LEFT JOIN card c ON (c.id = p.cardid)
			WHERE NOT is_basic_land(c.id)"""
	qargs = ()
	if printingid is not None:
		qry += " AND p.id = %s"
		qargs += (printingid,)
	qry += " ORDER BY EXISTS(SELECT 1 FROM user_card WHERE printingid=c.id) DESC, c.name ASC"
	cards = fetch_query(qry, qargs)

	tcgplayer_token = tcgplayer.login()

	asynchro.fetch_prices.delay(cards, tcgplayer_token)

	return jsonify()


@app.route('/update_rates', methods=['POST'])
@check_celery_running
def update_rates():
	asynchro.fetch_rates.delay()
	return jsonify()


@app.route('/refresh', methods=['POST'])
@login_required
def refresh():
	params = params_to_dict(request.form)
	asynchro.refresh_from_scryfall.delay(params['query'])
	return jsonify()


@app.route('/decks', methods=['GET'])
@login_required
def decks():
	return render_template('decks.html', active='decks')


@app.route('/decks/<int:deckid>', methods=['GET'])
@login_required
def decklist(deckid):
	formats = deck.get_formats()
	return render_template('decklist.html', deckid=deckid, formats=formats)


@app.route('/decks/get/all', methods=['GET'])
@login_required
def decks_get_all():
	params = params_to_dict(request.args, bool_keys=['deleted'])
	results = deck.get_all(params['deleted'])
	for r in results:
		if r['cardid']:
			if not os.path.exists(asynchro.card_art_filename(r['cardid'])):
				asynchro.get_card_art.delay(r['cardid'], r['code'], r['collectornumber'])
			r['arturl'] = url_for('static', filename='images/card_art_{}.jpg'.format(r['cardid']))
			del r['code']
			del r['collectornumber']

		r['viewurl'] = url_for('decklist', deckid=r['id'])
		del r['cardid']

	return jsonify(results=results)


@app.route('/decks/get', methods=['GET'])
@login_required
def decks_get():
	params = params_to_dict(request.args)
	resp = {}
	resp['deck'] = deck.get(params['deckid'])
	resp['main'], resp['sideboard'] = deck.get_cards(params['deckid'])

	if not os.path.exists(asynchro.card_art_filename(resp['deck']['cardid'])):
		asynchro.get_card_art.delay(
			resp['deck']['cardid'],
			resp['deck']['code'],
			resp['deck']['collectornumber']
		)
	resp['deck']['arturl'] = url_for('static', filename='images/card_art_{}.jpg'.format(resp['deck']['cardid']))
	del resp['deck']['cardid']
	del resp['deck']['code']
	del resp['deck']['collectornumber']

	resp['main'] = deck.parse_types(resp['main'])
	resp['sideboard'] = deck.parse_types(resp['sideboard'])

	return jsonify(**resp)


@app.route('/decks/save', methods=['POST'])
@login_required
def decks_save():
	params = params_to_dict(request.form)
	qry = "UPDATE deck SET name = %s, formatid = %s WHERE id = %s AND userid = %s"
	qargs = (params['name'], params['formatid'], params['deckid'], session['userid'],)
	mutate_query(qry, qargs)
	return jsonify()


@app.route('/decks/delete', methods=['POST'])
@login_required
def decks_delete():
	params = params_to_dict(request.form)
	mutate_query("UPDATE deck SET deleted = true WHERE id = %s AND userid = %s", (params['deckid'], session['userid'],))
	return jsonify()


@app.route('/decks/restore', methods=['POST'])
@login_required
def decks_restore():
	params = params_to_dict(request.form)
	mutate_query("UPDATE deck SET deleted = false WHERE id = %s AND userid = %s", (params['deckid'], session['userid'],))
	return jsonify()


@app.route('/decks/cardart', methods=['POST'])
@login_required
def decks_set_cardart():
	params = params_to_dict(request.form)
	mutate_query(
		"UPDATE deck SET cardartid = %s WHERE id = %s AND userid = %s",
		(params['cardid'], params['deckid'], session['userid'],)
	)
	return jsonify()


@app.route('/decks/cards/delete', methods=['POST'])
@login_required
def decks_cards_delete():
	params = params_to_dict(request.form)
	mutate_query(
		"""
		DELETE FROM deck_card
		WHERE id = %s
		AND (SELECT userid FROM deck WHERE deck.id = deckid) = %s
		""",
		(params['deck_cardid'], session['userid'],)
	)
	return jsonify()


@app.route('/decks/import', methods=['POST'])
@login_required
def decks_import():
	import csv

	filename = '/tmp/upload_%s_%s.csv' % (os.urandom(32), session['userid'])
	request.files['upload'].save(filename)
	rows = []
	with open(filename) as csvfile:
		importreader = csv.DictReader(csvfile)
		for row in importreader:
			rows.append(row)
	os.remove(filename)

	qry = """INSERT INTO deck (name, userid, formatid)
			VALUES (concat('Imported Deck ', to_char(now(), 'YYYY-MM-DD HH12:MI:SS')), %s, (SELECT id FROM format WHERE name = 'Other'))
			RETURNING id"""
	deckid = mutate_query(qry, (session['userid'],), returning=True)['id']

	for row in rows:
		print(row)
		qry = """INSERT INTO deck_card (deckid, cardid, quantity, section)
				VALUES (%s, deck_card_match(%s, %s), %s, %s)"""
		qargs = (deckid, row['Name'], session['userid'], row['Count'], row['Section'],)
		mutate_query(qry, qargs)

	qry = """UPDATE deck SET cardartid = (
				SELECT id FROM card WHERE EXISTS (
					SELECT 1 FROM deck_card WHERE cardid = card.id AND deckid = deck.id
				) ORDER BY random() LIMIT 1
			) WHERE id = %s"""
	mutate_query(qry, (deckid,))

	return jsonify()


if __name__ == '__main__':
	app.run()
