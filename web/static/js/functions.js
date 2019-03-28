function compile_handlebars(template_id, destination_selector, data) {
	var template = Handlebars.compile(document.getElementById(template_id).innerHTML);
	$(destination_selector).html(template(data));
}

function show_loading(elem) {
	compile_handlebars('loading-template', elem, {});
}

function ajax_failed(jqXHR) {
	// Only shows error message if not user aborted
	if (jqXHR.getAllResponseHeaders()) M.toast({html: "An internal error occurred. Please try again later."});
}

function is_mobile() {
	if(/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ) {
		return true;
	}
	return false;
}

$('.validate').on('keyup', function() {
	$(this).removeClass('valid invalid');
});

function check_form_valid(form) {
	var valid = true;
	form.find('.validate').removeClass('valid invalid').each(function() {
		if ($(this).val()) $(this).addClass('valid');
		else {
			$(this).addClass('invalid');
			valid = false;
		}
	});

	return valid;
}

$('.sidenav').sidenav();

document.addEventListener('DOMContentLoaded', function() {
	M.Modal.init(document.querySelectorAll('.modal'));
});