
def make_float(val: any) -> float:
	try:
		val = float(val)
	except TypeError:
		pass
	return val


def pagecount(count: int, limit: int) -> int:
	import math
	pages = 0
	if count:
		pages = count / limit
		if pages > 0 and pages < 1:
			pages = 1
		else:
			# Checking for overflow
			if limit % count != 0:
				pages = math.ceil(pages)
	return int(pages)
