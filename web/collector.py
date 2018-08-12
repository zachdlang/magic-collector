
from web.utility import *
from web import scryfall

collector = Blueprint('collector', __name__)


@collector.route('/login', methods=['GET','POST'])
def login():
	if is_logged_in():
		return redirect(url_for('collector.home'))

	if request.method == 'POST':
		params = params_to_dict(request.form)
		cursor = g.conn.cursor()
		cursor.execute("""SELECT * FROM app.enduser WHERE TRIM(username) = TRIM(%s)""", (params['username'],))
		resp = query_to_dict_list(cursor)[0]
		ok, new_hash = g.passwd_context.verify_and_update(params['password'].strip(), resp['password'].strip())
		if ok:
			if new_hash:
				cursor.execute("""UPDATE app.enduser SET password = %s WHERE id = %s""", (new_hash, resp['id'],))
				g.conn.commit()
			session.new = True
			session.permanent = True
			session['userid'] = resp['id']
		cursor.close()
			
		if ok:
			return redirect(url_for('collector.home'))
		else:
			flash('Login failed.', 'danger')
			return redirect(url_for('collector.login'))

	return render_template('login.html')


@collector.route('/logout', methods=['GET'])
def logout():
	session.pop('userid', None)
	return redirect(url_for('collector.login'))


@collector.route('/', methods=['GET'])
@login_required
def home():
	return render_template('collector.html')


@collector.route('/csv_upload', methods=['GET'])
@login_required
def csv_upload():
	import csv
	multiverse_ids = []
	with open('/home/zach/Downloads/Bulk.csv') as csvfile:
		importreader = csv.DictReader(csvfile)
		for row in importreader:
			# print(row['MultiverseID'], row['Name'], row['Edition code'], row['Quantity'], row['Foil'])
			multiverse_ids.append({ 'multiverse_id':int(row['MultiverseID'])})
	bulk_lots = ([ multiverse_ids[i:i + 75] for i in range(0, len(multiverse_ids), 75) ])
	for lot in bulk_lots:
		resp = scryfall.get_bulk(lot)
		import_cards(resp)

	return jsonify(resp)


def import_cards(cards):
	cursor = g.conn.cursor()
	sets = []
	for c in cards:
		if c['set'] not in [ x['code'] for x in sets ]:
			sets.append({ 'code':c['set'], 'name':c['set_name'] })

	for s in sets:
		qry = """INSERT INTO card_set (name, code) SELECT %s, %s 
				WHERE NOT EXISTS (SELECT * FROM card_set WHERE code = %s)"""
		qargs = (s['name'], s['code'], s['code'],)
		cursor.execute(qry, qargs)
		g.conn.commit()
		
	for c in cards:
		print(c)
		qry = """INSERT INTO card (
				collectornumber, multiverseid, name, card_setid, colors,
				cmc, manacost, power, toughness, rarity, 
				multifaced, typeline, oracletext, flavortext, artist) SELECT
				%s, %s, %s, (SELECT id FROM card_set WHERE code = %s), %s,
				%s, %s, %s, %s, %s,
				%s, %s, %s, %s, %s
				WHERE NOT EXISTS (SELECT * FROM card WHERE multiverseid = %s)"""
		qargs = (c['collectornumber'], c['multiverseid'], c['name'], c['set'], c['colors'],
				c['cmc'], c['manacost'], c['power'], c['toughness'], c['rarity'],
				c['multifaced'], c['typeline'], c['oracletext'], c['flavortext'], c['artist'],
				c['multiverseid'],)
		cursor.execute(qry, qargs)
		g.conn.commit()
	cursor.close()
