
from web.utility import *

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
