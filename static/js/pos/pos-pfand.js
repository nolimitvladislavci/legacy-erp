/* ═══ POS Pfand Return Modal (Unified) ═══
 * Shared across quick.html, restaurant.html, receipt.html
 * addPfandReturn() is defined per-view in their respective JS files
 */
(function(){
  var _pfandItems = null;
  var apiBase = (window.location.pathname.match(/^\/([a-z]{2})\//) || ['',''])[1];
  apiBase = apiBase ? '/' + apiBase : '';

  window.openPfandModal = function() {
    var modal = document.getElementById("pfandModal");
    if (!modal) return;
    if (modal.classList) modal.classList.add("show"); else modal.style.display = 'flex';
    if (_pfandItems === null) {
      fetch(apiBase + "/pos/api/pfand-items/")
        .then(function(r){ return r.json(); })
        .then(function(data){ _pfandItems = data.items || []; renderPfandList(); });
    } else { renderPfandList(); }
  };

  window.openPfandReturn = window.openPfandReturn || window.openPfandModal;

  window.closePfandModal = function() {
    var modal = document.getElementById("pfandModal");
    if (!modal) return;
    if (modal.classList) modal.classList.remove("show"); else modal.style.display = 'none';
  };

  function renderPfandList() {
    var el = document.getElementById("pfandList");
    if (!el) return;
    if (!_pfandItems || !_pfandItems.length) {
      el.innerHTML = '<div style="color:var(--muted);text-align:center;padding:1rem">Nema pfand artikala.</div>';
      return;
    }
    el.innerHTML = _pfandItems.map(function(it) {
      return '<div style="display:flex;align-items:center;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid var(--border)">' +
        '<div><div style="font-size:.85rem;font-weight:600">' + it.name + '</div>' +
        '<div style="font-size:.7rem;color:var(--muted)">-' + parseFloat(it.unit_price).toFixed(2) + ' €</div></div>' +
        '<button onclick="addPfandReturn(' + it.id + ',\'' + it.name.replace(/'/g, "\\'") + '\',' + it.unit_price + ')" ' +
        'style="background:var(--green);color:#000;border:none;padding:.4rem .8rem;border-radius:6px;font-weight:700;font-size:.8rem;cursor:pointer">+ Dodaj</button></div>';
    }).join('');
  }
})();
