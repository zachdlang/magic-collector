
def make_float(val):
	try:
		val = float(val)
	except TypeError:
		pass
	return val
