var sets_loaded = false;

$(document).ready(function() {
	get_collection();

	$('#filter_rarity').formSelect();

	bind_events();
});

document.addEventListener('DOMContentLoaded', function() {
	M.Materialbox.init(document.querySelectorAll('#view_box'), {
		onOpenStart: function() { $('#view_box').removeClass('hide'); },
		onCloseStart: function() { $('#view_box').addClass('hide'); }
	});
});

function get_sets() {
	$.ajax({
		url: "/get_sets",
		method: "GET"
	}).done(function(data) {
		if (data.error) M.toast({html: data.error});
		else {
			compile_handlebars('filtersets-template', '#filter_set', data);
			$('#filter_set').formSelect();
			sets_loaded = true;
		}
	}).fail(ajax_failed);
}

var search_req;
var current_page = 1;
var sort = 'name';
var sort_desc = 'asc';
function get_collection() {
	if (search_req) search_req.abort();
	$('#collection_head').addClass('hide');
	show_loading($('#collection_list'));
	$('#collection_pagination, #collection_total').empty();

	search_req = $.ajax({
		url: "/get_collection",
		method: "GET",
		data: {
			'page': current_page,
			'sort': sort,
			'sort_desc': sort_desc,
			'filter_search': $('#search-row-search').val(),
			'filter_set': $('#filter_set_value').val(),
			'filter_rarity': $('#filter_rarity_value').val()
		}
	}).done(function(data) {
		if (data.error) M.toast({html: data.error});
		else {
			$('#collection_head').removeClass('hide');
			compile_handlebars('collection-template', '#collection_list', data);

			$('#collection_list .name').hover(function() {
				var image_url = $(this).closest('tr').data().image;
				var vert_pos = $(this).position().top - $(this).height() - 65;
				var horiz_pos = $(this).position().left + $(this).width();
				compile_handlebars('hover-template', $(this).find('.card-hover-img'), {
					'vert_pos': vert_pos,
					'horiz_pos': horiz_pos,
					'image_url': image_url
				});
				$('#view_box').attr('src', image_url);
			}, function() {
				$('.card-hover').remove();
			});

			generate_pagination($('#collection_pagination'), data.count);
			compile_handlebars('collectiontotal-template', '#collection_total', data);
		}
	}).fail(ajax_failed);
}

function generate_pagination(elem, count) {
	var data = {};
	data['pages'] = [];

	if (current_page > 1) {
		data['pages'].push({'class': 'first-page', 'icon': 'first_page'});
		data['pages'].push({'class': 'prev-page', 'icon': 'chevron_left'});
	}

	var max_back = 2;
	var max_forward = 3;
	if (current_page - max_back > 1) data['pages'].push({
		'class': 'dropdown-trigger',
		'label': '...',
		'target': 'extra-pages-before'
	});

	for (var i = current_page - max_back; i < current_page + max_forward; i++) {
		if (i > 0 && i <= count) {
			var page = {'class': 'page', 'label': i};
			if (i == current_page) page['active'] = true;
			data['pages'].push(page);
		}
	}

	if (current_page + max_forward < count) data['pages'].push({
		'class': 'dropdown-trigger',
		'label': '...',
		'target': 'extra-pages-after'
	});

	if (current_page < count) {
		data['pages'].push({'class': 'next-page', 'icon': 'chevron_right'});
		data['pages'].push({'class': 'last-page', 'icon': 'last_page'});
	}

	data['extras_before'] = [];
	data['extras_after'] = [];
	for (var i = 1; i <= count; i++) {
		if (i < current_page - max_back) data['extras_before'].push({'class': 'page', 'label': i});
		if (i >= current_page + max_forward) data['extras_after'].push({'class': 'page', 'label': i});
	}

	compile_handlebars('pagination-template', elem, data);
	
	var elems = document.querySelectorAll('.dropdown-trigger');
	var instances = M.Dropdown.init(elems, {'container': $('body')});

	elem.off('click');
	elem.on('click', '.first-page', function() {
		current_page = 1;
		get_collection();
	});
	elem.on('click', '.prev-page', function() {
		current_page--;
		get_collection();
	});
	elem.on('click', '.next-page', function() {
		current_page++;
		get_collection();
	});
	elem.on('click', '.last-page', function() {
		current_page = count;
		get_collection();
	});
}

function bind_events() {
	$('#filter-row-button').on('click', function() {
		if (!sets_loaded) get_sets();
		M.Modal.getInstance($('#filter_modal')).open();
	});

	$('.sort-head').on('click', function() {
		console.log('here');
		sort = $(this).data().sort_col;
		if ($(this).hasClass('valign-wrapper')) {
			if (sort_desc == 'asc') sort_desc = 'desc';
			else sort_desc = 'asc';
		} else {
			sort_desc = 'asc';
		}

		// Reset sort classes etc
		$('.sort-head').removeClass('valign-wrapper').find('.material-icons').remove();

		$(this).addClass('valign-wrapper').append('<i class="material-icons"></i>');
		if (sort_desc === 'asc') $(this).find('.material-icons').html('keyboard_arrow_up');
		else $(this).find('.material-icons').html('keyboard_arrow_down')

		get_collection();
	});

	$('#collection_list').on('click', '.name', function() {
		// Only show hover for mobile due to glitchy-ness
		if (is_mobile()) $(this).hover();
		else M.Materialbox.getInstance($('#view_box')).open();
	});

	$('#collection_list').on('click', '.edit-card', function() {
		// Clear out to account for loading delays
		$('#edit_modal .art').attr('src', '');

		var row = $(this).closest('tr');
		$('#edit_modal .art').attr('src', row.data().art);
		$('#edit_modal .name').text(row.find('.name').text());
		$('#edit_modal .quantity').val(row.find('.quantity').text());
		$('#edit_modal .foil').prop('checked', row.data().foil === 1);
		$('#edit_modal .user_cardid').val(row.data().usercard_id);
		M.Modal.getInstance($('#edit_modal')).open();
	});

	var search_timer;
	$('#search-row-search').on('keyup', function() {
		current_page = 1;
		if ($(this).val().length >= 3 || $(this).val().length == 0) {
			clearTimeout(search_timer);
			search_timer = setTimeout(function() {
				$('#search-row-button').click();
			}, 250);
		}
	});

	$('#search-row-button').on('click', function() {
		get_collection();
	});

	$('#add-row-show').on('click', function() {
		$('#add-row').removeClass('hide');
		$('#search-row').addClass('hide');
	});

	$('#add-row-hide').on('click', function() {
		$('#add-row').addClass('hide');
		$('#search-row').removeClass('hide');
		$('#search-results-dismiss').click();
	});

	var add_search_req;
	var add_search_timer;
	$('#add-row-search').on('keyup', function() {
		if ($(this).val().length >= 3 || $(this).val().length == 0) {
			var query = $(this).val()
			clearTimeout(add_search_timer);
			add_search_timer = setTimeout(function() {
				if (add_search_req) add_search_req.abort();
				add_search_req = $.ajax({
					url: "/search",
					method: "GET",
					data: { 'query':query }
				}).done(function(data) {
					$('#search-results').removeClass('hide');
					compile_handlebars('search-template', '#search-results-list', data);
				}).fail(ajax_failed);
		    }, 250);
		}
	});

	$('#search-results-dismiss').on('click', function() {
		$('#search-results').addClass('hide');
		$('#search-results-list').empty();
	});

	$('#search-results-list').on('click', '.search-results-add', function() {
		var cardname = $(this).closest('tr').find('.cardname').text();
		var cardid = $(this).data().cardid;
		var foil = false;
		var quantity = 1;
		$.ajax({
			url: "/collection/card/add",
			method: "POST",
			data: {
				'cardid': cardid,
				'foil': foil,
				'quantity': quantity
			}
		}).done(function(data) {
			if (data.error) M.toast({html: data.error});
			else {
				var success_str = cardname + " (x" + quantity + ")";
				if (foil === 1) success_str = "Foil " + success_str;
				M.toast({html: "Added " + success_str + " successfully."});
				$('#search-row-search').val($('#add-row-search').val());
				get_collection();
			}
		}).fail(ajax_failed);
	});

	$('#edit_btn').on('click', function() {
		$.ajax({
			url: "/collection/card/edit",
			method: "POST",
			data: {
				'user_cardid': $('#edit_modal .user_cardid').val(),
				'quantity': $('#edit_modal .quantity').val(),
				'foil': $('#edit_modal .foil').prop('checked')
			}
		}).done(function(data) {
			if (data.error) M.toast({html: data.error});
			else {
				M.toast({html: "Saved successfully."});
				get_collection();
				M.Modal.getInstance($('#edit_modal')).close();
			}
		}).fail(ajax_failed)
	});

	$('#upload_btn').on('click', function() {
		show_loading($('#upload_loading'));
		var form = document.forms.namedItem('upload_form');
		var formdata = new FormData(form);

		var upload_req = new XMLHttpRequest();
		upload_req.open("POST", "/csv_upload", true);
		upload_req.onload = function(oEvent) {
			$('#upload_loading').empty();
			if (upload_req.status == 200) {
				M.Modal.getInstance($('#upload_modal')).close();
				M.toast({html: "Successfully Uploaded"});
				get_collection();
			} else {
				M.toast({html: "An internal error occurred. Please try again later."});
			}
		};

		upload_req.send(formdata);
	});

	$('#filter_btn').on('click', function() {
		var filters = [];
		$('#filter_modal select').each(function() {
			if ($(this).val()) {
				var filter_key = $(this).attr('id');
				var selected = $(this).find('option:selected');
				filters.push({
					'key': filter_key,
					'value': selected.attr('value'),
					'label': selected.text(),
					'icon': selected.attr('data-icon')
				});
			}
		});

		compile_handlebars('filterchip-template', '#filter-chips', {'filters': filters});

		if ($('#filter-chips .chip').length === -1) $('#filter-chips').addClass('hide');
		else $('#filter-chips').removeClass('hide');

		M.Modal.getInstance($('#filter_modal')).close();
		get_collection();
	});

	$(document).on('click', '.filter-remove', function() {
		var chip = $(this).closest('.chip');
		console.log(chip.find('input').data().orig);
		$(chip.find('input').data().orig).val('').formSelect();
		chip.remove();
		if ($('#filter-chips .chip').length <= 0) $('#filter-chips').empty().addClass('hide');
		get_collection();
	});

	// Outside of pagination function as Materialize
	// dropdown won't be in pagination element
	$(document).on('click', '.page', function() {
		current_page = parseInt($(this).text());
		get_collection();
	});
}
