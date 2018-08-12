
CREATE TABLE IF NOT EXISTS enduser (
	id SERIAL primary key,
	firstname TEXT NOT NULL,
	surname TEXT NOT NULL,
	email TEXT NOT NULL,
	username TEXT NOT NULL,
	password TEXT NOT NULL,
	ipaddr INET
)WITH OIDS;

CREATE TABLE IF NOT EXISTS card_set (
	id SERIAL primary key,
	name TEXT NOT NULL,
	code TEXT NOT NULL
)WITH OIDS;

CREATE TABLE IF NOT EXISTS card (
	id SERIAL primary key,
	collectornumber TEXT NOT NULL,
	multiverseid INTEGER NOT NULL,
	name TEXT NOT NULL,
	card_setid INTEGER NOT NULL REFERENCES card_set(id) ON DELETE CASCADE,
	colors TEXT,
	cmc NUMERIC,
	manacost TEXT,
	power TEXT,
	toughness TEXT,
	rarity CHARACTER,
	multifaced BOOLEAN NOT NULL DEFAULT FALSE,
	typeline TEXT,
	oracletext TEXT,
	flavortext TEXT,
	artist TEXT
)WITH OIDS;
