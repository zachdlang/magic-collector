# Standard library imports
import logging
from logging.handlers import SMTPHandler

# Third party imports
from flask import Flask, request, session, g, jsonify, send_from_directory
from passlib.context import CryptContext
import psycopg2
import psycopg2.extras

# Local imports
from web.collector import collector
from web.utility import (
	is_logged_in, get_file_location
)


class BetterExceptionFlask(Flask):
	def log_exception(self, exc_info):
		"""Overrides log_exception called by flask to give more information
		in exception emails.
		"""
		err_text = """
URL:                  %s%s
HTTP Method:          %s
Client IP Address:    %s

request.form:
%s

request.args:
%s

session:
%s

""" % (
			request.host, request.path,
			request.method,
			request.remote_addr,
			request.form,
			request.args,
			session,
		)

		self.logger.critical(err_text, exc_info=exc_info)


app = BetterExceptionFlask(__name__)

app.config.from_pyfile('site_config.cfg')
app.secret_key = app.config['SECRETKEY']

app.register_blueprint(collector, url_prefix='')

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
	g.passwd_context = CryptContext().from_path(get_file_location('/passlibconfig.ini'))
	g.config = app.config


@app.route('/favicon.ico')
@app.route('/robots.txt')
@app.route('/sitemap.xml')
def static_from_root():
	return send_from_directory(app.static_folder, request.path[1:])


if __name__ == '__main__':
	app.run()
