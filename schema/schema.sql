
CREATE TABLE IF NOT EXISTS enduser (
	id SERIAL primary key,
	firstname TEXT NOT NULL,
	surname TEXT NOT NULL,
	email TEXT NOT NULL,
	username TEXT NOT NULL,
	password TEXT NOT NULL,
	ipaddr INET
)WITH OIDS;

CREATE TABLE IF NOT EXISTS subscription (
	id SERIAL primary key,
	enduserid INTEGER NOT NULL REFERENCES enduser(id) ON DELETE CASCADE,
	name TEXT,
	url TEXT NOT NULL,
	refreshed TIMESTAMP NOT NULL DEFAULT now(),
	category TEXT
)WITH OIDS;