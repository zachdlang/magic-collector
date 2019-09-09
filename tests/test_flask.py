from web import app


def test_flask_alive():
	test_client = app.test_client()
	resp = test_client.get('/ping')
	assert(resp.json == {'ping': 'pong'})
