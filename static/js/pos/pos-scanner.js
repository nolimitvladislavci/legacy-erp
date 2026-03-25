/* ═══ POS Scanner — ZXing + AI fallback ═══
 * Extracted from quick.html scanner block
 * Requires html5-qrcode.min.js loaded before this
 */
(function(){
  var _langPrefix = (window.location.pathname.match(/^\/([a-z]{2})\//) || ['',''])[1];
  _langPrefix = _langPrefix ? '/' + _langPrefix : '';
  var CSRF = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  var _scanReader = null;
  var _scanActive = false;
  var _lastCode   = '';
  var _lastCodeTs = 0;
  var _pendingBarcode = '';

  window.openScanner = function() {
    document.getElementById('scannerOverlay').style.display = 'block';
    document.getElementById('scannerResult').textContent = '';
    document.getElementById('manualBarcode').value = '';
    document.getElementById('scannerVideo').style.display = 'block';
    _startZXing();
  };

  function _startZXing() {
    if (typeof Html5Qrcode === 'undefined') { _scannerFallback('Scanner library nije dostupan'); return; }
    try {
      _scanReader = new Html5Qrcode('scannerVideo');
      _scanActive = true;
      _scanReader.start(
        { facingMode: 'environment' },
        { fps: 10, qrbox: { width: 280, height: 160 }, formatsToSupport: [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15], experimentalFeatures: { useBarCodeDetectorIfSupported: true } },
        function(code) {
          if (!_scanActive) return;
          var now = Date.now();
          if (code === _lastCode && now - _lastCodeTs < 1500) return;
          _lastCode = code; _lastCodeTs = now;
          _onCodeDetected(code);
        },
        function() {}
      ).catch(function(e) { _scannerFallback(e); });
      _setScanStatus('Usmjeri kameru na barkod ili QR kod', '#c9a84c');
    } catch(e) { _scannerFallback(e.message || e); }
  }

  function _scannerFallback() {
    document.getElementById('scannerVideo').style.display = 'none';
    _setScanStatus('Kamera nedostupna — unesi barkod ručno', '#f59e0b');
    setTimeout(function(){ document.getElementById('manualBarcode').focus(); }, 100);
  }

  window.closeScanner = function() {
    _scanActive = false;
    document.getElementById('scannerOverlay').style.display = 'none';
    if (_scanReader) { try { _scanReader.stop().catch(function(){}); } catch(e) {} _scanReader = null; }
    _lastCode = ''; _lastCodeTs = 0;
  };

  function _onCodeDetected(code) {
    var codeType = _classifyBarcode(code);
    if (codeType === 'skip') { _setScanStatus('Preskoceno: neispravan kod', '#666'); return; }
    if (codeType === 'document') { _setScanStatus('Barkod dokumenta — nije artikl', '#a78bfa'); _flashOverlay('#a78bfa'); return; }
    if (codeType === 'qr_url') { _setScanStatus('QR link: ' + code.substring(0, 40) + '...', '#3b82f6'); _flashOverlay('#3b82f6'); return; }
    _setScanStatus('Trazim artikl: ' + code + ' (' + codeType + ')', '#c9a84c');
    var xhr = new XMLHttpRequest();
    xhr.open('GET', _langPrefix + '/pos/api/barcode/?barcode=' + encodeURIComponent(code), true);
    xhr.withCredentials = true; xhr.timeout = 5000;
    xhr.onload = function() {
      try {
        var data = JSON.parse(xhr.responseText);
        if (data.found && data.id) {
          _addScannedProduct(data);
          _setScanStatus('Dodan: ' + data.name + ' (' + data.price + ' EUR)', '#22c55e');
          _flashOverlay('#22c55e');
          try { new Audio('data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=').play(); } catch(e){}
        } else { _setScanStatus('Barkod ' + code + ' nije u bazi', '#f59e0b'); _showNewItemOption(code); }
      } catch(e) { _setScanStatus('Greska servera', '#ef4444'); _flashOverlay('#ef4444'); }
    };
    xhr.onerror = function() { _setScanStatus('Nema veze sa serverom', '#ef4444'); };
    xhr.ontimeout = function() { _setScanStatus('Server ne odgovara', '#ef4444'); };
    xhr.send();
  }

  function _classifyBarcode(code) {
    if (!code || code.length < 3) return 'skip';
    if (code.startsWith('http://') || code.startsWith('https://')) return 'qr_url';
    var isNumeric = /^\d+$/.test(code);
    if (isNumeric) {
      if (code.length === 8) return 'EAN-8';
      if (code.length === 13) return 'EAN-13';
      if (code.length === 12) return 'UPC-A';
      if (code.length === 14) return 'ITF-14';
      if (code.length > 16) return 'document';
      if (code.length >= 4 && code.length <= 7) return 'interni';
    }
    if (code.length <= 20) return 'Code128';
    if (code.length > 20) return 'document';
    return 'nepoznat';
  }

  function _addScannedProduct(data) {
    var btn = document.getElementById('pb-' + data.id);
    if (btn && typeof window.addProduct === 'function') { window.addProduct(btn); return; }
    var tempBtn = document.createElement('button');
    tempBtn.dataset.id = data.id; tempBtn.dataset.name = data.name;
    tempBtn.dataset.price = data.price; tempBtn.dataset.tax = data.tax_rate || 25;
    tempBtn.dataset.weighable = '0'; tempBtn.style.display = 'none';
    document.body.appendChild(tempBtn);
    if (typeof window.addProduct === 'function') window.addProduct(tempBtn);
    tempBtn.remove();
  }

  function _setScanStatus(msg, color) {
    var el = document.getElementById('scannerResult');
    if (el) { el.textContent = msg; el.style.color = color || '#fff'; }
  }

  function _flashOverlay(color) {
    var overlay = document.getElementById('scannerOverlay');
    var orig = overlay.style.background;
    overlay.style.background = color + '22';
    setTimeout(function(){ overlay.style.background = orig; }, 200);
  }

  function _showNewItemOption(code) {
    _pendingBarcode = code;
    _setScanStatus('Barkod ' + code + ' nije u bazi — popunite formu', '#f59e0b');
    document.getElementById('newItemBarcode').textContent = code;
    document.getElementById('newItemPanel').style.display = 'block';
    document.getElementById('newItemLoading').style.display = 'none';
    document.getElementById('newItemForm').style.display = 'block';
    document.getElementById('niName').value = '';
    document.getElementById('niPrice').value = '';
    document.getElementById('niAiHint').textContent = 'AI analizira...';
    document.getElementById('niName').focus();
    _scanActive = false;
    try { _aiRecognizeProduct(code); } catch(e) {}
  }

  function _aiRecognizeProduct(code) {
    var videoEl = document.querySelector('#scannerVideo video') || document.getElementById('scannerVideo');
    var canvas = document.createElement('canvas');
    if (videoEl && videoEl.videoWidth) {
      canvas.width = videoEl.videoWidth; canvas.height = videoEl.videoHeight;
      canvas.getContext('2d').drawImage(videoEl, 0, 0);
    } else {
      document.getElementById('niAiHint').textContent = 'Unesite podatke rucno';
      document.getElementById('niName').focus(); return;
    }
    var imageData = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
    fetch('/pos/api/ai-barcode/', { method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': CSRF}, body: JSON.stringify({code: code, image: imageData, recognize_product: true}) })
    .then(function(r) { return r.json(); }).then(function(data) {
      document.getElementById('newItemLoading').style.display = 'none';
      document.getElementById('newItemForm').style.display = 'block';
      document.getElementById('niName').value = data.name || '';
      document.getElementById('niPrice').value = data.price || '';
      if (data.category) { var sel = document.getElementById('niCategory'); for (var i = 0; i < sel.options.length; i++) { if (sel.options[i].value === data.category) { sel.selectedIndex = i; break; } } }
      document.getElementById('niAiHint').textContent = data.name ? 'AI prepoznao: ' + data.name + ' — provjerite' : 'AI nije prepoznao — unesite rucno';
      document.getElementById('niName').focus();
    }).catch(function() {
      document.getElementById('newItemLoading').style.display = 'none';
      document.getElementById('newItemForm').style.display = 'block';
      document.getElementById('niAiHint').textContent = 'Unesite podatke rucno';
      document.getElementById('niName').focus();
    });
  }

  window.confirmNewItem = function() {
    var name = document.getElementById('niName').value.trim();
    var price = document.getElementById('niPrice').value.trim();
    var category = document.getElementById('niCategory').value;
    var vat = document.getElementById('niVat').value;
    if (!name) { document.getElementById('niName').focus(); return; }
    if (!price) { document.getElementById('niPrice').focus(); return; }
    var xhr = new XMLHttpRequest();
    xhr.open('POST', _langPrefix + '/pos/api/quick-add-item/', true);
    xhr.withCredentials = true;
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('X-CSRFToken', CSRF);
    xhr.onload = function() {
      try {
        var data = JSON.parse(xhr.responseText);
        if (data.id) {
          _addScannedProduct({id: data.id, name: name, price: parseFloat(price), tax_rate: parseInt(vat)});
          _setScanStatus('Novi artikl "' + name + '" spremljen i dodan!', '#22c55e');
          _flashOverlay('#22c55e'); cancelNewItem();
        } else { fenixToast('Greska: ' + (data.error || xhr.responseText.substring(0, 100, 'error'))); }
      } catch(e) { fenixToast('Greska: ' + xhr.status, 'error'); }
    };
    xhr.onerror = function() { fenixToast('Greska veze', 'error'); };
    xhr.send(JSON.stringify({ name: name, price: parseFloat(price), category: category, tax_rate: parseInt(vat), barcode: _pendingBarcode }));
  };

  window.cancelNewItem = function() {
    document.getElementById('newItemPanel').style.display = 'none';
    _pendingBarcode = ''; _scanActive = true; _lastCode = ''; _lastCodeTs = 0;
  };

  window.aiSnapAndRecognize = function() {
    var btn = document.getElementById('btnAiSnap');
    var label = document.getElementById('aiSnapLabel');
    label.textContent = 'AI analizira...'; btn.disabled = true;
    _setScanStatus('Slikam i saljem AI-u...', '#7c3aed');
    var videoEl = document.querySelector('#scannerVideo video');
    if (!videoEl) { var videos = document.querySelectorAll('#scannerVideo video, video'); for (var v = 0; v < videos.length; v++) { if (videos[v].videoWidth > 0) { videoEl = videos[v]; break; } } }
    var imageData = '';
    if (videoEl && videoEl.videoWidth > 0) {
      var canvas = document.createElement('canvas'); canvas.width = videoEl.videoWidth; canvas.height = videoEl.videoHeight;
      canvas.getContext('2d').drawImage(videoEl, 0, 0);
      imageData = canvas.toDataURL('image/jpeg', 0.85).split(',')[1];
    }
    if (!imageData) {
      var inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'image/*'; inp.capture = 'environment';
      inp.onchange = function() { if (!inp.files[0]) { btn.disabled = false; label.textContent = 'Slikaj i prepoznaj (AI)'; return; } var reader = new FileReader(); reader.onload = function(e) { _sendToAI(e.target.result.split(',')[1], btn, label); }; reader.readAsDataURL(inp.files[0]); };
      inp.click(); return;
    }
    _sendToAI(imageData, btn, label);
  };

  function _sendToAI(imageData, btn, label) {
    _setScanStatus('AI analizira sliku...', '#7c3aed');
    var xhr = new XMLHttpRequest();
    xhr.open('POST', _langPrefix + '/pos/api/ai-barcode/', true);
    xhr.withCredentials = true; xhr.setRequestHeader('Content-Type', 'application/json'); xhr.setRequestHeader('X-CSRFToken', CSRF); xhr.timeout = 15000;
    xhr.onload = function() {
      btn.disabled = false; label.textContent = 'Slikaj i prepoznaj (AI)';
      try {
        var data = JSON.parse(xhr.responseText);
        if (data.code) {
          _setScanStatus('AI procitao: ' + data.code + (data.name ? ' — ' + data.name : ''), '#7c3aed');
          document.getElementById('manualBarcode').value = data.code;
          var lxhr = new XMLHttpRequest();
          lxhr.open('GET', _langPrefix + '/pos/api/barcode/?barcode=' + encodeURIComponent(data.code), true);
          lxhr.withCredentials = true;
          lxhr.onload = function() {
            try {
              var ldata = JSON.parse(lxhr.responseText);
              if (ldata.found && ldata.id) { _addScannedProduct(ldata); _setScanStatus('AI pronasao: ' + ldata.name + ' — dodan!', '#22c55e'); _flashOverlay('#22c55e'); }
              else { _showNewItemOption(data.code); if (data.name) document.getElementById('niName').value = data.name; if (data.price) document.getElementById('niPrice').value = data.price; document.getElementById('niAiHint').textContent = 'AI prepoznao: ' + (data.name || data.code); }
            } catch(e) { _showNewItemOption(data.code); }
          };
          lxhr.send();
        } else if (data.name) {
          _setScanStatus('AI prepoznao: ' + data.name + ' (barkod necitljiv)', '#f59e0b');
          _showNewItemOption(''); document.getElementById('niName').value = data.name;
          if (data.price) document.getElementById('niPrice').value = data.price;
          document.getElementById('niAiHint').textContent = 'AI prepoznao proizvod ali nije procitao barkod';
        } else { _setScanStatus('AI nije prepoznao — pokusajte ponovo', '#ef4444'); }
      } catch(e) { _setScanStatus('Greska AI', '#ef4444'); }
    };
    xhr.onerror = function() { btn.disabled = false; label.textContent = 'Slikaj i prepoznaj (AI)'; _setScanStatus('Nema veze sa AI', '#ef4444'); };
    xhr.ontimeout = function() { btn.disabled = false; label.textContent = 'Slikaj i prepoznaj (AI)'; _setScanStatus('AI predugo odgovara', '#f59e0b'); };
    xhr.send(JSON.stringify({code: '', image: imageData, recognize_product: true}));
  }

  window.manualLookup = function() {
    var code = document.getElementById('manualBarcode').value.trim(); if (!code) return;
    _lastCode = ''; _lastCodeTs = 0;
    var mxhr = new XMLHttpRequest();
    mxhr.open('GET', _langPrefix + '/pos/api/barcode/?barcode=' + encodeURIComponent(code), true);
    mxhr.withCredentials = true;
    mxhr.onload = function() {
      try {
        var data = JSON.parse(mxhr.responseText);
        if (data.found && data.id) { _addScannedProduct(data); _setScanStatus('Dodan: ' + data.name, '#22c55e'); _flashOverlay('#22c55e'); document.getElementById('manualBarcode').value = ''; }
        else { _showNewItemOption(code); }
      } catch(e) { _showNewItemOption(code); }
    };
    mxhr.onerror = function() { _showNewItemOption(code); };
    mxhr.send();
  };

  document.addEventListener('keydown', function(e) { if (e.key === 'F2') { e.preventDefault(); openScanner(); } });
})();
