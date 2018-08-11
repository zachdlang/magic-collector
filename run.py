#!/usr/bin/python3
from web import app

import os

extra_dirs = ['web/templates']
extra_files = []
for extra_dir in extra_dirs:
	for dirname, dirs, files in os.walk(extra_dir):
		for filename in files:
			filename = os.path.join(dirname, filename)
			if os.path.isfile(filename):
				extra_files.append(filename)

app.run(debug=True, port=9000, extra_files=extra_files)
