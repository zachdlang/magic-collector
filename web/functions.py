
def make_float(val: any) -> float:
	try:
		val = float(val)
	except TypeError:
		pass
	return val
