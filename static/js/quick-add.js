/**
 * QuickAdd — reusable modal for quickly creating records via JSON API.
 *
 * Usage:
 *   QuickAdd.open({
 *     title:     'Novi partner',
 *     fields:    [ {name:'name', label:'Naziv', required:true},
 *                  {name:'oib',  label:'OIB'},
 *                  {name:'email',label:'E-mail', type:'email'} ],
 *     apiUrl:    '/partners/api/quick-create/',
 *     csrfToken: document.querySelector('[name=csrfmiddlewaretoken]').value,
 *     onSuccess: function(data) { console.log(data); }
 *   });
 */
(function(global) {
  'use strict';

  var _modal = null;
  var _cfg   = null;

  function _build() {
    var backdrop = document.createElement('div');
    backdrop.id = 'quickAddBackdrop';
    backdrop.style.cssText = [
      'position:fixed',
      'inset:0',
      'background:rgba(0,0,0,.65)',
      'z-index:10000',
      'display:flex',
      'align-items:center',
      'justify-content:center',
    ].join(';');

    var box = document.createElement('div');
    box.id = 'quickAddBox';
    box.style.cssText = [
      'background:#1a1a1a',
      'border:1px solid #333',
      'border-radius:12px',
      'padding:28px',
      'min-width:360px',
      'max-width:480px',
      'width:90%',
      'position:relative',
    ].join(';');

    box.innerHTML =
      '<h5 id="qaTitle" style="color:#c9a84c;margin-bottom:18px"></h5>' +
      '<div id="qaFields"></div>' +
      '<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px">' +
        '<button id="qaCancel" class="btn btn-sm btn-secondary">Odustani</button>' +
        '<button id="qaSave"   class="btn btn-sm btn-warning"><i class="fas fa-save me-1"></i>Spremi</button>' +
      '</div>' +
      '<div id="qaError" style="color:#f87171;font-size:.82rem;margin-top:10px;display:none"></div>';

    backdrop.appendChild(box);
    document.body.appendChild(backdrop);

    document.getElementById('qaCancel').addEventListener('click', _close);
    backdrop.addEventListener('click', function(e) {
      if (e.target === backdrop) _close();
    });
    document.getElementById('qaSave').addEventListener('click', _save);

    return backdrop;
  }

  function _close() {
    if (_modal) _modal.style.display = 'none';
  }

  function _save() {
    var errEl = document.getElementById('qaError');
    errEl.style.display = 'none';
    var payload = {};
    var valid = true;
    (_cfg.fields || []).forEach(function(f) {
      var el = document.getElementById('qa_' + f.name);
      if (!el) return;
      var val = el.value.trim();
      if (f.required && !val) {
        errEl.textContent = (f.label || f.name) + ' je obavezno polje.';
        errEl.style.display = 'block';
        el.focus();
        valid = false;
      }
      payload[f.name] = val;
    });
    if (!valid) return;

    var saveBtn = document.getElementById('qaSave');
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Sprema...';

    var csrf = _cfg.csrfToken ||
      (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '';

    fetch(_cfg.apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
      },
      body: JSON.stringify(payload),
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      saveBtn.disabled = false;
      saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>Spremi';
      if (data.ok) {
        _close();
        if (typeof _cfg.onSuccess === 'function') _cfg.onSuccess(data);
        _toast(data.status === 'created' ? 'Kreiran: ' : 'Postoji: ', data.name || '');
      } else {
        errEl.textContent = data.error || 'Greska pri pohrani.';
        errEl.style.display = 'block';
      }
    })
    .catch(function() {
      saveBtn.disabled = false;
      saveBtn.innerHTML = '<i class="fas fa-save me-1"></i>Spremi';
      errEl.textContent = 'Mrezna greska. Pokusajte ponovo.';
      errEl.style.display = 'block';
    });
  }

  function _toast(prefix, name) {
    var t = document.createElement('div');
    t.style.cssText = [
      'position:fixed',
      'bottom:24px',
      'right:24px',
      'background:#166534',
      'color:#fff',
      'padding:12px 20px',
      'border-radius:8px',
      'z-index:99999',
      'font-size:.9rem',
    ].join(';');
    t.innerHTML = '<i class="fas fa-check me-2"></i>' + prefix + '<strong>' + name + '</strong>';
    document.body.appendChild(t);
    setTimeout(function() { t.remove(); }, 3500);
  }

  var QuickAdd = {
    open: function(cfg) {
      _cfg = cfg || {};
      if (!_modal) _modal = _build();

      document.getElementById('qaTitle').innerHTML =
        (cfg.icon ? '<i class="' + cfg.icon + ' me-2"></i>' : '') + (cfg.title || 'Dodaj zapis');

      var fieldsEl = document.getElementById('qaFields');
      fieldsEl.innerHTML = '';
      (_cfg.fields || []).forEach(function(f) {
        var wrap = document.createElement('div');
        wrap.className = 'mb-3';
        var lbl = document.createElement('label');
        lbl.style.cssText = 'color:#ccc;font-size:.85rem';
        lbl.textContent = f.label + (f.required ? ' *' : '');
        var inp = document.createElement('input');
        inp.id = 'qa_' + f.name;
        inp.type = f.type || 'text';
        inp.className = 'form-control form-control-sm';
        inp.value = f.default || '';
        if (f.placeholder) inp.placeholder = f.placeholder;
        wrap.appendChild(lbl);
        wrap.appendChild(inp);
        fieldsEl.appendChild(wrap);
      });

      document.getElementById('qaError').style.display = 'none';
      document.getElementById('qaSave').disabled = false;
      document.getElementById('qaSave').innerHTML = '<i class="fas fa-save me-1"></i>Spremi';
      _modal.style.display = 'flex';

      var first = fieldsEl.querySelector('input');
      if (first) setTimeout(function() { first.focus(); }, 80);
    },
    close: _close,
  };

  global.QuickAdd = QuickAdd;
})(window);
