
DROP FUNCTION IF EXISTS collector.get_collectornumber(INTEGER);
CREATE OR REPLACE FUNCTION collector.get_collectornumber(_cardid INTEGER) RETURNS TEXT AS $$
	SELECT CASE WHEN multifaced = true THEN
		concat(collectornumber, 'a')
	ELSE
		collectornumber
	END FROM card WHERE id = _cardid;
$$ LANGUAGE 'sql';

DROP FUNCTION IF EXISTS collector.get_price(INTEGER);
CREATE OR REPLACE FUNCTION collector.get_price(_user_cardid INTEGER) RETURNS MONEY AS $$
	SELECT CASE WHEN foil = true THEN
		foilprice
	ELSE
		price
	END FROM card, user_card WHERE cardid = card.id AND user_card.id = _user_cardid;
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