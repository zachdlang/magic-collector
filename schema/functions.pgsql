
DROP FUNCTION IF EXISTS collector.get_collectornumber(INTEGER);
CREATE OR REPLACE FUNCTION collector.get_collectornumber(_printingid INTEGER) RETURNS TEXT AS $$
	SELECT CASE WHEN c.multifaced = true THEN
		concat(p.collectornumber, 'a')
	ELSE
		p.collectornumber
	END FROM printing p LEFT JOIN card c ON (c.id = p.cardid) WHERE p.id = _printingid;
$$ LANGUAGE 'sql';


CREATE OR REPLACE FUNCTION collector.convert_price(_amount MONEY, _userid INTEGER) RETURNS MONEY AS $$
	SELECT _amount * COALESCE(
		(SELECT exchangerate FROM currency WHERE code =
			(SELECT currencycode FROM app.enduser WHERE id = _userid)
		),
		1
	);
$$ LANGUAGE 'sql';


DROP FUNCTION IF EXISTS collector.get_price(INTEGER);
CREATE OR REPLACE FUNCTION collector.get_price(_user_cardid INTEGER) RETURNS MONEY AS $$
	SELECT CASE WHEN foil = true THEN
		convert_price(foilprice, userid)
	ELSE
		convert_price(price, userid)
	END
	FROM printing, user_card WHERE printingid = printing.id AND user_card.id = _user_cardid;
$$ LANGUAGE 'sql';


DROP FUNCTION IF EXISTS collector.set_price(INTEGER, MONEY, MONEY, TEXT);
CREATE OR REPLACE FUNCTION collector.set_price(
	_printingid INTEGER,
	_price MONEY,
	_foilprice MONEY,
	_pricetype TEXT
) RETURNS VOID AS $$
BEGIN
	UPDATE printing SET price = _price, foilprice = _foilprice WHERE id = _printingid;

	INSERT INTO price_history (printingid, price, foilprice, pricetype)
		SELECT _printingid, _price, _foilprice, _pricetype
		WHERE NOT EXISTS (
			SELECT 1 FROM price_history WHERE printingid = _printingid AND created = current_date
		);

	RETURN;
END;
$$ LANGUAGE 'plpgsql';


DROP FUNCTION IF EXISTS collector.is_basic_land(INTEGER);
CREATE OR REPLACE FUNCTION collector.is_basic_land(_cardid INTEGER) RETURNS BOOLEAN AS $$
	SELECT typeline ILIKE '%basic%land%' FROM card WHERE id = _cardid;
$$ LANGUAGE 'sql';


DROP FUNCTION IF EXISTS collector.get_rarity(TEXT);
CREATE OR REPLACE FUNCTION collector.get_rarity(_initial TEXT) RETURNS TEXT AS $$
	SELECT CASE
	WHEN _initial = 'C' THEN 'Common'
	WHEN _initial = 'U' THEN 'Uncommon'
	WHEN _initial = 'R' THEN 'Rare'
	WHEN _initial = 'M' THEN 'Mythic'
	END;
$$ LANGUAGE 'sql';


DROP FUNCTION IF EXISTS collector.update_rates(TEXT, NUMERIC);
CREATE OR REPLACE FUNCTION collector.update_rates(_code TEXT, _exchangerate NUMERIC) RETURNS VOID AS $$
BEGIN
	IF EXISTS (SELECT * FROM currency WHERE UPPER(code) = UPPER(_code)) THEN
		UPDATE currency SET exchangerate = _exchangerate WHERE UPPER(code) = UPPER(_code);
	ELSE
		INSERT INTO currency (code, exchangerate) VALUES (UPPER(_code), _exchangerate);
	END IF;
	RETURN;
END;
$$ LANGUAGE 'plpgsql';


DROP FUNCTION IF EXISTS collector.deck_card_match(TEXT, INTEGER);
CREATE OR REPLACE FUNCTION collector.deck_card_match(_name TEXT, _userid INTEGER) RETURNS INTEGER AS $$
DECLARE
	cardid INTEGER;
BEGIN
	SELECT c.id INTO cardid FROM card c WHERE LOWER(c.name) = LOWER(_name);

	-- If no matches, ILIKE for multifaced cards
	IF cardid IS NULL THEN
		SELECT c.id INTO cardid
			FROM card c
			WHERE c.multifaced AND c.name ILIKE concat('%', _name, '%');
	END IF;

	RETURN cardid;
END;
$$ LANGUAGE 'plpgsql';


DROP FUNCTION IF EXISTS collector.card_owned(INTEGER, INTEGER);
CREATE OR REPLACE FUNCTION collector.card_owned(_userid INTEGER, _printing INTEGER)
RETURNS BOOLEAN AS $$
	SELECT EXISTS (SELECT 1 FROM user_card WHERE userid = _userid AND printingid = _printing);
$$ LANGUAGE 'sql';


DROP FUNCTION IF EXISTS collector.total_printings_owned(INTEGER, INTEGER);
CREATE OR REPLACE FUNCTION collector.total_printings_owned(_userid INTEGER, _cardid INTEGER)
RETURNS INTEGER AS $$
	SELECT COALESCE(
		(SELECT SUM(quantity) FROM user_card uc WHERE uc.userid = _userid AND uc.printingid IN (
			SELECT id FROM printing WHERE cardid = _cardid
		)
	), 0)::INTEGER; 
$$ LANGUAGE 'sql';


DROP FUNCTION IF EXISTS collector.get_format(INTEGER);
CREATE OR REPLACE FUNCTION collector.get_format(_formatid INTEGER) RETURNS TEXT AS $$
	SELECT name FROM format WHERE id = _formatid;
$$ LANGUAGE 'sql';
