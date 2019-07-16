$(document).ready(function() {
	show_details();

	bind_events();
});


function show_details() {
	show_loading($('#deck-details .deck-list'));

	$.ajax({
		url: "/decks/get",
		method: "GET",
		data: {'deckid': $('#deckid').val()}
	}).done(function(data) {
		if (data.error) M.toast({html: data.error});
		else {
			$('#edit-deck-art').attr('src', data.deck.arturl);
			var elems = document.querySelectorAll('.parallax');
			M.Parallax.init(elems, {});

			$('#edit-deck-name').val(data.deck.name);
			$('#edit-deck-format').val(data.deck.formatid);
			Handlebars.registerPartial('cardlist', $('#cardlist-partial').html());
			compile_handlebars('editdeck-template', '#deck-details .deck-list', data);
			
			$('#deck-details .deck-info #edit-deck-format').formSelect();
			if (data.deck.deleted) $('#deck-restore').removeClass('hide');
			else $('#deck-delete').removeClass('hide');

			// Hide sideboard if not applicable
			if (!$('#list-sideboard tbody tr').length) {
				$('#list-sideboard').addClass('hide');
			}

			$('#deck-details .deck-list tbody tr').on('click', function() {
				var cardid = $(this).data().cardid;
				if (cardid) set_arturl(cardid);
			});
		}
	}).fail(ajax_failed);
}

function set_arturl(cardid) {
	$.ajax({
		url: "/decks/cardart",
		method: "POST",
		data: {
			'deckid': $('#deckid').val(),
			'cardid': cardid
		}
	}).done(function(data) {
		if (data.error) M.toast({html: data.error});
		else window.location.reload();
	}).fail(ajax_failed);
}


function bind_events() {
	$('#deck-save').on('click', function() {
		$.ajax({
			url: "/decks/save",
			method: "POST",
			data: {
				'deckid': $('#deckid').val(),
				'name': $('#edit-deck-name').val(),
				'formatid': $('#edit-deck-format').val()
			}
		}).done(function(data) {
			if (data.error) M.toast({html: data.error});
			else M.toast({html: 'Saved successfully.'});
		}).fail(ajax_failed);
	});

	$('#deck-delete').on('click', function() {
		$.ajax({
			url: "/decks/delete",
			method: "POST",
			data: {'deckid': $('#deckid').val()}
		}).done(function(data) {
			if (data.error) M.toast({html: data.error});
			else window.location.replace('/decks')
		}).fail(ajax_failed);
	});

	$('#deck-restore').on('click', function() {
		$.ajax({
			url: "/decks/restore",
			method: "POST",
			data: {'deckid': $('#deckid').val()}
		}).done(function(data) {
			if (data.error) M.toast({html: data.error});
			else window.location.replace('/decks')
		}).fail(ajax_failed);
	});

	$('#deck-back').on('click', function() {
		window.location.href = '/decks';
	});
}
