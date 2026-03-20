/** Extracted from arhiva_convert.html */
var CSRF = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
var _lm = window.location.pathname.match(/^\/([a-z]{2})\//);
var API = _lm ? '/' + _lm[1] : '';
var _pcfg = document.getElementById('page-config');
var URL_ARHIVA = _pcfg ? JSON.parse(_pcfg.textContent).arhivaListUrl || '' : '';
var _files = [];

// ── File handling ────────────────────────────────────────────────────────────
var zone = document.getElementById('uploadZone');
var fin = document.getElementById('fileInput');
var cam = document.getElementById('cameraInput');

['dragenter','dragover'].forEach(function(e) { zone.addEventListener(e, function(ev) { ev.preventDefault(); zone.classList.add('dragover'); }); });
['dragleave','drop'].forEach(function(e) { zone.addEventListener(e, function(ev) { ev.preventDefault(); zone.classList.remove('dragover'); }); });
zone.addEventListener('drop', function(ev) { Array.from(ev.dataTransfer.files).forEach(addFile); });
fin.addEventListener('change', function() { Array.from(this.files).forEach(addFile); });
cam.addEventListener('change', function() { if (this.files[0]) addFile(this.files[0]); });

// Android fallback: page restore after camera
window.addEventListener('pageshow', function() { if (cam.files && cam.files[0] && !_files.length) addFile(cam.files[0]); });
document.addEventListener('visibilitychange', function() { if (!document.hidden && cam.files && cam.files[0] && !_files.length) addFile(cam.files[0]); });

function addFile(file) {
  if (!file.type.startsWith('image/')) { alert('Samo slike.'); return; }
  if (file.size > 10*1024*1024) { alert('Prevelika: ' + file.name); return; }
  _files.push(file);
  renderPhotos();
}

function removeFile(i) {
  _files.splice(i, 1);
  if (!_files.length) { resetForm(); return; }
  renderPhotos();
}

function renderPhotos() {
  var grid = document.getElementById('photoGrid');
  grid.innerHTML = '';
  _files.forEach(function(f, i) {
    var d = document.createElement('div'); d.className = 'thumb';
    var img = document.createElement('img'); img.alt = f.name;
    var r = new FileReader();
    r.onload = function(e) { img.src = e.target.result; };
    r.readAsDataURL(f);
    var btn = document.createElement('button'); btn.className = 'rm'; btn.type = 'button';
    btn.innerHTML = '&times;'; btn.onclick = function() { removeFile(i); };
    d.appendChild(img); d.appendChild(btn); grid.appendChild(d);
  });
  document.getElementById('photoCount').textContent = _files.length;
  document.getElementById('previewInfo').textContent = _files.length + ' slika · ' + (_files.reduce(function(s,f){return s+f.size;},0)/1024).toFixed(0) + ' KB';
  document.getElementById('uploadArea').style.display = 'none';
  document.getElementById('imgPreview').style.display = 'block';
  setStage(1);
}

// ── Konverzija ───────────────────────────────────────────────────────────────
async function startConvert() {
  if (!_files.length) return;
  document.getElementById('imgPreview').style.display = 'none';
  document.getElementById('cvProgress').style.display = 'block';
  document.getElementById('cvResult').style.display = 'none';

  var results = [];
  for (var idx = 0; idx < _files.length; idx++) {
    var file = _files[idx];
    var pct = Math.round((idx / _files.length) * 80);
    document.getElementById('progressBar').style.width = pct + '%';
    document.getElementById('progressLabel').textContent = (_files.length > 1 ? (idx+1) + '/' + _files.length + ': ' : '') + file.name;
    document.getElementById('progressDetail').textContent = 'AI ekstrakcija...';
    setStage(idx === 0 ? 2 : 3);
    try {
      var fd = new FormData();
      fd.append('file', file);
      fd.append('csrfmiddlewaretoken', CSRF);
      var res = await fetch(API + '/documents/arhiva/convert/', {
        method:'POST', credentials:'same-origin',
        headers:{'X-Requested-With':'XMLHttpRequest'}, body:fd
      });
      var data = await res.json();
      results.push({file:file.name, data:data});
    } catch(e) {
      results.push({file:file.name, data:{error:e.message}});
    }
  }
  document.getElementById('progressBar').style.width = '100%';
  setStage(5, true);
  setTimeout(function() {
    document.getElementById('cvProgress').style.display = 'none';
    showResults(results);
  }, 300);
}

// ── Rezultat ─────────────────────────────────────────────────────────────────
function showResults(results) {
  var el = document.getElementById('cvResult');
  el.style.display = 'block';

  if (results.length === 1) {
    showSingle(results[0].data);
    return;
  }

  // Multi
  var ok = results.filter(function(r){return !r.data.error && r.data.is_valid;}).length;
  var warn = results.filter(function(r){return !r.data.error && !r.data.is_valid;}).length;
  var err = results.filter(function(r){return r.data.error;}).length;
  el.className = 'cv-result ' + (err ? 'warn' : 'ok');
  document.getElementById('resultBadge').className = 'badge badge-ok';
  document.getElementById('resultBadge').textContent = results.length + ' obradeno';
  document.getElementById('resultMsg').textContent = ok + ' uspjesno, ' + warn + ' upozorenja, ' + err + ' gresaka';
  document.getElementById('resultGrid').innerHTML =
    '<div class="result-stat"><span class="lbl">Obradeno</span><span class="val">' + results.length + '</span></div>' +
    '<div class="result-stat"><span class="lbl">Uspjesno</span><span class="val" style="color:#10b981">' + ok + '</span></div>' +
    '<div class="result-stat"><span class="lbl">Upozorenja</span><span class="val" style="color:#f59e0b">' + warn + '</span></div>' +
    '<div class="result-stat"><span class="lbl">Greske</span><span class="val" style="color:#ef4444">' + err + '</span></div>';
  var html = '';
  results.forEach(function(r) {
    var icon = r.data.error ? '!' : (r.data.is_valid ? '+' : '?');
    html += '<div style="display:flex;align-items:center;gap:.5rem;padding:.4rem 0;border-bottom:1px solid var(--border);font-size:.82rem">' +
      '<span style="color:' + (r.data.error?'#ef4444':r.data.is_valid?'#10b981':'#f59e0b') + ';font-weight:700">' + icon + '</span>' +
      '<span style="flex:1">' + r.file + '</span>' +
      (r.data.error ? '<span style="color:#ef4444;font-size:.75rem">' + r.data.error + '</span>' : '') +
      '</div>';
  });
  document.getElementById('resultExtras').innerHTML = html;
  document.getElementById('resultActions').innerHTML =
    '<button onclick="resetForm()" class="btn-gold"><i class="fas fa-redo"></i> Nova konverzija</button>' +
    '<a href="' + URL_ARHIVA + '" class="btn-ghost"><i class="fas fa-archive"></i> Otvori arhivu</a>';
}

function showSingle(data) {
  var el = document.getElementById('cvResult');
  el.className = 'cv-result';

  if (data.error) {
    el.classList.add('err');
    document.getElementById('resultBadge').className = 'badge badge-err';
    document.getElementById('resultBadge').textContent = 'Greska';
    document.getElementById('resultMsg').textContent = data.error;
    document.getElementById('resultGrid').innerHTML = '';
    document.getElementById('resultExtras').innerHTML = '';
    document.getElementById('resultActions').innerHTML =
      '<button onclick="resetForm()" class="btn-gold"><i class="fas fa-redo"></i> Pokusaj ponovo</button>';
    return;
  }

  el.classList.add(data.is_valid ? 'ok' : 'warn');
  document.getElementById('resultBadge').className = 'badge ' + (data.is_valid ? 'badge-ok' : 'badge-warn');
  document.getElementById('resultBadge').textContent = data.is_valid ? 'Spremljeno u arhivu' : 'Spremljeno (s upozorenjima)';
  document.getElementById('resultMsg').textContent = data.message || '';

  var conf = 0;
  if (data.confidence_score != null) {
    var cs = parseFloat(data.confidence_score);
    conf = cs > 1 ? cs.toFixed(0) : (cs * 100).toFixed(0);
  }

  document.getElementById('resultGrid').innerHTML =
    '<div class="result-stat"><span class="lbl">Pouzdanost</span><span class="val">' + conf + '%</span></div>' +
    '<div class="result-stat"><span class="lbl">Usteda</span><span class="val">' + (data.savings||'-') + '</span></div>' +
    '<div class="result-stat"><span class="lbl">Polja</span><span class="val">' + (data.fields_extracted||0) + '</span></div>' +
    '<div class="result-stat"><span class="lbl">Stavke</span><span class="val">' + (data.items_extracted||0) + '</span></div>' +
    '<div class="result-stat"><span class="lbl">Smanjenje</span><span class="val">' + (data.size_reduction_pct||0) + '%</span></div>';

  var html = '';
  if (data.validation_errors && data.validation_errors.length) {
    html += '<details><summary>Upozorenja (' + data.validation_errors.length + ')</summary><pre>' + data.validation_errors.join('\n') + '</pre></details>';
  }
  if (data.extracted_data) {
    html += '<details><summary>Ekstrahirani podaci</summary><pre>' + JSON.stringify(data.extracted_data, null, 2) + '</pre></details>';
  }
  document.getElementById('resultExtras').innerHTML = html;

  document.getElementById('resultActions').innerHTML =
    '<button onclick="resetForm()" class="btn-gold"><i class="fas fa-redo"></i> Nova konverzija</button>' +
    '<a href="' + URL_ARHIVA + '" class="btn-ghost"><i class="fas fa-archive"></i> Otvori arhivu</a>';
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function setStage(n, allDone) {
  for (var i = 1; i <= 5; i++) {
    var s = document.getElementById('st' + i);
    s.className = 'stage';
    if (allDone) s.classList.add('done');
    else if (i < n) s.classList.add('done');
    else if (i === n) s.classList.add('active');
  }
}

// ── QR Remote Scan ────────────────────────────────────────────────────────
var _qrToken = null;
var _qrPollInterval = null;
var _qrCountdown = null;
var _qrSeconds = 600;

function startQRScan() {
  fetch(API + '/documents/scan/create-token/', {
    credentials: 'same-origin',
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    _qrToken = data.token;
    _qrSeconds = data.expires_in || 600;
    document.getElementById('qrImage').src = data.qr_data;
    document.getElementById('qrModal').style.display = 'block';
    document.getElementById('uploadZone').style.display = 'none';

    // Start polling every 2 sec
    _qrPollInterval = setInterval(pollForScan, 2000);

    // Countdown
    _qrCountdown = setInterval(function() {
      _qrSeconds--;
      var m = Math.floor(_qrSeconds / 60);
      var s = _qrSeconds % 60;
      document.getElementById('qrTimer').textContent = 'Istice za: ' + m + ':' + (s < 10 ? '0' : '') + s;
      if (_qrSeconds <= 0) cancelQRScan();
    }, 1000);
  })
  .catch(function(e) { alert('Greska: ' + e.message); });
}

function pollForScan() {
  if (!_qrToken) return;
  fetch(API + '/documents/scan/' + _qrToken + '/poll/', {
    credentials: 'same-origin',
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.ready) {
      cancelQRScan();
      document.getElementById('qrModal').style.display = 'none';
      if (data.converted) {
        setStage(5, true);
        showSingle(data);
      } else if (data.error) {
        showSingle({error: data.error});
      }
    }
  })
  .catch(function() {});
}

function cancelQRScan() {
  if (_qrPollInterval) { clearInterval(_qrPollInterval); _qrPollInterval = null; }
  if (_qrCountdown) { clearInterval(_qrCountdown); _qrCountdown = null; }
  _qrToken = null;
  document.getElementById('qrModal').style.display = 'none';
  document.getElementById('uploadZone').style.display = '';
}

function resetForm() {
  _files = [];
  fin.value = ''; cam.value = '';
  document.getElementById('uploadArea').style.display = '';
  document.getElementById('imgPreview').style.display = 'none';
  document.getElementById('cvProgress').style.display = 'none';
  document.getElementById('cvResult').style.display = 'none';
  setStage(1);
  window.scrollTo({top:0, behavior:'smooth'});
}
