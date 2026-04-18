/* ═══ POS Fiscal Shield Widget ═══
 * Shared between quick.html and restaurant.html
 * Polls /pos/fiscal/status-api/ every 15s
 */
(function shieldInit(){
  var langPrefix = (window.location.pathname.match(/^\/([a-z]{2})\//) || ['',''])[1];
  var apiBase = langPrefix ? '/' + langPrefix : '';

  function updateShield(){
    fetch(apiBase + '/pos/fiscal/status-api/')
      .then(function(r){ return r.json(); })
      .then(function(d){
        var dot   = document.getElementById('shield-dot');
        var ring  = document.getElementById('shield-ring');
        var txt   = document.getElementById('shield-badge-text');
        var badge = document.getElementById('shield-badge');
        if (!dot) return;
        if (d.pending > 0) {
          dot.className = 'shield-warn';
          ring.style.borderColor = '#ef4444';
          if (txt) { txt.textContent = d.pending + ' ČEKA'; txt.style.color = '#ef4444'; }
          if (badge) { badge.textContent = d.pending + ' ČEKA'; badge.style.background = '#ef4444'; badge.style.display = 'block'; }
        } else {
          dot.className = 'shield-ok';
          ring.style.borderColor = '#c9a84c';
          if (txt) { txt.textContent = 'Fiskal'; txt.style.color = '#c9a84c'; }
          if (badge) { badge.style.display = 'none'; }
        }
      }).catch(function(){});
  }
  updateShield();
  setInterval(updateShield, 15000);
})();
