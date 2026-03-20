/**
 * fina-utils.js — Globalni JS utilitiji za LIMIT Connect
 *
 * Korištenje:
 *   new FinaOibLookup('oibInputId', options)
 *   new FinaNkdSearch('searchInputId', 'hiddenInputId', options)
 */

// ── OIB Lookup ────────────────────────────────────────────────────────────────

function FinaOibLookup(oibInputId, options) {
  options = options || {};
  var oibInput = document.getElementById(oibInputId);
  if (!oibInput) return;

  var btn  = document.getElementById(options.btnId  || (oibInputId + 'Btn'));
  var icon = document.getElementById(options.iconId || (oibInputId + 'Icon'));
  var feed = document.getElementById(options.feedId || (oibInputId + 'Feedback'));
  var countryInputName = options.countryInputName || 'country';

  function setFeedback(msg, type) {
    if (!feed) return;
    var icons = {success:'check-circle', danger:'exclamation-circle', warning:'exclamation-triangle', info:'info-circle'};
    feed.innerHTML = msg
      ? '<span class="text-' + type + '"><i class="fas fa-' + (icons[type]||'info-circle') + '"></i> ' + msg + '</span>'
      : '';
  }

  function fillForm(data) {
    var form = oibInput.closest('form') || document.querySelector('form');
    if (!form) return;
    function set(name, val) {
      var el = form.querySelector('[name="' + name + '"]');
      if (el && val) el.value = val;
    }
    if (options.onFill) {
      options.onFill(data, set);
    } else {
      set('name',     data.name);
      set('address',  data.address);
      set('city',     data.city);
      set('zip_code', data.zip_code);
      set('country',  data.country || 'Hrvatska');
      if (data.email) set('email', data.email);
    }
  }

  function doLookup() {
    var oib = oibInput.value.trim();
    if (!oib) { setFeedback('Unesite OIB ili VAT broj', 'warning'); return; }
    if (oib.length > 13) { setFeedback('OIB/VAT ne smije biti duži od 13 znakova', 'danger'); return; }

    if (btn)  btn.disabled = true;
    if (icon) icon.className = 'fas fa-spinner fa-spin';
    setFeedback('Pretraživanje...', 'info');

    var form = oibInput.closest('form') || document.querySelector('form');
    var countryEl = form ? form.querySelector('[name="' + countryInputName + '"]') : null;
    var country = ((countryEl ? countryEl.value : '').trim().substring(0, 2).toUpperCase()) || 'HR';

    fetch('/partners/api/oib-lookup/?oib=' + encodeURIComponent(oib) + '&country=' + country, {
      headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (btn)  btn.disabled = false;
      if (icon) icon.className = 'fas fa-search';
      if (data.found) {
        fillForm(data);
        var msg = data.source === 'database'
          ? 'Partner pronađen u bazi — podaci popunjeni'
          : 'Tvrtka pronađena u registru — podaci popunjeni';
        setFeedback(msg, 'success');
        if (options.onSuccess) options.onSuccess(data);
      } else if (data.not_vat_registered) {
        // OIB je ispravan ali firma nije PDV obveznik — dozvoli ručni unos
        setFeedback('⚠️ OIB je ispravan, ali firma nije PDV obveznik (nije u EU VIES registru). Unesite podatke ručno.', 'warning');
        // Popuni samo OIB polje da korisnik ne mora ponovo tipkati
        var oibField = oibInput.closest('form') ? oibInput.closest('form').querySelector('[name="oib"]') : null;
        if (oibField && !oibField.value) oibField.value = oib;
        if (options.onNotFound) options.onNotFound(data);
      } else if (data.error && !data.oib_valid) {
        setFeedback(data.error, 'danger');
      } else {
        setFeedback('Tvrtka nije pronađena u registru. Možete unijeti podatke ručno.', 'warning');
      }
    })
    .catch(function() {
      if (btn)  btn.disabled = false;
      if (icon) icon.className = 'fas fa-search';
      setFeedback('Greška pri spajanju na registar', 'danger');
    });
  }

  if (btn) btn.addEventListener('click', doLookup);

  oibInput.addEventListener('input', function() {
    var val = this.value.trim();
    if (val.length > 13) {
      this.value = val.substring(0, 13);
      setFeedback('OIB/VAT ne smije biti duži od 13 znakova', 'danger');
      return;
    }
    if (val.length === 11 && /^\d{11}$/.test(val)) doLookup();
  });

  oibInput.addEventListener('paste', function() {
    setTimeout(function() {
      var val = oibInput.value.trim();
      if (val.length >= 8) doLookup();
    }, 60);
  });

  this.lookup = doLookup;
}


// ── NKD Search ────────────────────────────────────────────────────────────────

function FinaNkdSearch(searchInputId, hiddenInputId, options) {
  options = options || {};
  var searchInput = document.getElementById(searchInputId);
  var hiddenInput = document.getElementById(hiddenInputId);
  if (!searchInput) return;

  var dropdownId = options.dropdownId || (searchInputId + 'Dropdown');
  var dropdown = document.getElementById(dropdownId);
  if (!dropdown) {
    dropdown = document.createElement('div');
    dropdown.id = dropdownId;
    dropdown.className = 'position-absolute bg-white border rounded shadow-sm';
    dropdown.style.cssText = 'width:100%;max-height:240px;overflow-y:auto;z-index:1050;display:none';
    var wrapper = searchInput.parentElement;
    if (window.getComputedStyle(wrapper).position === 'static') {
      wrapper.style.position = 'relative';
    }
    wrapper.appendChild(dropdown);
  }

  var debounceTimer = null;

  function showDropdown(items) {
    if (!items.length) { dropdown.style.display = 'none'; return; }
    dropdown.innerHTML = items.map(function(item) {
      var name = (item.name_hr || item.name_en || '').replace(/"/g, '&quot;');
      return '<div class="px-3 py-2 nkd-opt" style="cursor:pointer;font-size:.84rem;border-bottom:1px solid #f0f0f0"'
        + ' data-id="' + item.id + '" data-code="' + item.code + '" data-name="' + name + '">'
        + '<span class="badge bg-secondary me-1" style="font-size:.7rem">' + item.code + '</span>'
        + (item.name_hr || item.name_en || '')
        + '</div>';
    }).join('');
    dropdown.style.display = 'block';

    dropdown.querySelectorAll('.nkd-opt').forEach(function(el) {
      el.addEventListener('mouseenter', function() { this.style.background = '#f8f9fa'; });
      el.addEventListener('mouseleave', function() { this.style.background = ''; });
      el.addEventListener('click', function() {
        var id   = this.dataset.id;
        var code = this.dataset.code;
        var name = this.dataset.name;
        if (hiddenInput) hiddenInput.value = id;
        searchInput.value = code + ' \u2014 ' + name;
        dropdown.style.display = 'none';
        if (options.onSelect) options.onSelect({id: id, code: code, name: name});
      });
    });
  }

  searchInput.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    var q = this.value.trim();
    if (q.length < 2) { dropdown.style.display = 'none'; return; }
    debounceTimer = setTimeout(function() {
      fetch('/companies/api/nkd-search/?q=' + encodeURIComponent(q), {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
      })
      .then(function(r) { return r.json(); })
      .then(function(data) { showDropdown(Array.isArray(data) ? data : (data.results || [])); })
      .catch(function() { dropdown.style.display = 'none'; });
    }, 280);
  });

  document.addEventListener('click', function(e) {
    if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.style.display = 'none';
    }
  });

  this.clear = function() {
    searchInput.value = '';
    if (hiddenInput) hiddenInput.value = '';
    dropdown.style.display = 'none';
  };
}
