/**
 * Blind Count (Slijepa Inventura) — inventory/blind_count.html
 * No Django template dependencies — pure JS.
 */
(function(){
'use strict';

var _siHistory = [];

window.siAlert = function(msg, type) {
    var el = document.getElementById('siAlert');
    var icons = {
        ok: 'fa-circle-check',
        kalo: 'fa-triangle-exclamation',
        theft: 'fa-shield-halved',
        quarantine: 'fa-biohazard',
        info: 'fa-circle-info'
    };
    el.innerHTML = '<i class="fa-solid ' + (icons[type] || icons.info) + '"></i>' + msg;
    el.className = 'si-alert si-alert-' + type;
    el.style.display = 'block';
};

function siClearAlert() {
    document.getElementById('siAlert').style.display = 'none';
}

function siSetLoading(loading) {
    var btn = document.getElementById('siBtn');
    var spinner = document.getElementById('siSpinner');
    var icon = document.getElementById('siBtnIcon');
    var txt = document.getElementById('siBtnText');
    btn.disabled = loading;
    spinner.style.display = loading ? 'inline-block' : 'none';
    icon.style.display = loading ? 'none' : '';
    txt.textContent = loading ? 'PROVJERA...' : 'Potvrdi Stanje';
}

window.siLookupBatch = function() {
    var batchId = document.getElementById('siBatchId').value.trim();
    var info = document.getElementById('siBatchInfo');
    if (!batchId) { info.style.display = 'none'; return; }

    fetch('/inventory/api/batch/' + batchId + '/check-dispatch/')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.item_name) {
                var statusTag = '';
                if (data.allowed === false) {
                    statusTag = '<span class="tag tag-quarantine">KARANTENA</span>';
                } else {
                    statusTag = '<span class="tag tag-active">AKTIVNA</span>';
                }
                info.innerHTML =
                    '<strong>' + data.item_name + '</strong> ' + statusTag + '<br>' +
                    'Sarza: ' + (data.batch_number || '-') +
                    (data.expiry_date ? ' | Rok: <strong>' + data.expiry_date + '</strong>' : '') +
                    (data.quantity ? ' | Kol: ' + data.quantity : '');
                info.style.display = 'block';
            }
        })
        .catch(function() { info.style.display = 'none'; });
};

window.siSubmit = function() {
    var batchId = document.getElementById('siBatchId').value.trim();
    var weight = document.getElementById('siWeight').value.trim();

    siClearAlert();

    if (!batchId) {
        siAlert('Unesite ili skenirajte ID sarze.', 'info');
        document.getElementById('siBatchId').focus();
        return;
    }
    if (!weight) {
        siAlert('Unos tezine s vage je OBAVEZAN. Potvrda bez mjerenja nije dozvoljena.', 'theft');
        document.getElementById('siWeight').focus();
        return;
    }

    siSetLoading(true);

    fetch('/inventory/api/submit-count/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': siGetCookie('csrftoken')
        },
        body: JSON.stringify({
            batch_id: parseInt(batchId),
            actual_weight: parseFloat(weight)
        })
    })
    .then(function(r) {
        return r.json().then(function(d) { return {ok: r.ok, status: r.status, data: d}; });
    })
    .then(function(res) {
        if (res.status === 409) {
            siAlert(res.data.error || 'UPOZORENJE: Utvrden kritican manjak!', 'theft');
            siAddHistory(batchId, weight, 'theft', res.data.difference_pct);
            document.getElementById('siWeight').value = '';
            document.getElementById('siWeight').focus();
            return;
        }
        if (res.status === 403) {
            siAlert(res.data.error || 'BLOKADA: Sarza u HACCP karanteni.', 'quarantine');
            siAddHistory(batchId, weight, 'quarantine', null);
            return;
        }
        if (res.status === 400) {
            siAlert(res.data.error || 'Neispravan format unosa.', 'info');
            return;
        }
        if (!res.ok) {
            siAlert(res.data.error || 'Greska na serveru.', 'theft');
            return;
        }

        var type = res.data.status === 'kalo' ? 'kalo' : 'ok';
        siAlert(res.data.message || 'Stanje uspjesno zabilježeno.', type);
        siAddHistory(batchId, weight, type, res.data.difference_pct);

        document.getElementById('siBatchId').value = '';
        document.getElementById('siWeight').value = '';
        document.getElementById('siBatchInfo').style.display = 'none';
        document.getElementById('siBatchId').focus();
    })
    .catch(function(err) {
        siAlert('Mrezna greska: ' + err.message, 'theft');
    })
    .finally(function() {
        siSetLoading(false);
    });
};

function siAddHistory(batchId, weight, result, diffPct) {
    _siHistory.unshift({
        batch: batchId, weight: weight, result: result,
        diff: diffPct,
        time: new Date().toLocaleTimeString('hr-HR', {hour:'2-digit', minute:'2-digit'})
    });
    if (_siHistory.length > 10) _siHistory.pop();
    siRenderHistory();
}

function siRenderHistory() {
    var card = document.getElementById('siHistoryCard');
    var wrap = document.getElementById('siHistory');
    if (_siHistory.length === 0) { card.style.display = 'none'; return; }
    card.style.display = 'block';

    var resultLabels = {ok: 'OK', kalo: 'Kalo', theft: 'ALARM', quarantine: 'Karantena'};
    var resultClasses = {ok: 'si-result-ok', kalo: 'si-result-kalo', theft: 'si-result-theft', quarantine: 'si-result-theft'};

    var html = '';
    _siHistory.forEach(function(h) {
        html += '<div class="si-history-row">' +
            '<span><strong>Sarza ' + h.batch + '</strong> &mdash; ' + h.weight + ' kg</span>' +
            '<span>' + h.time + ' <strong class="' + (resultClasses[h.result] || '') + '">' +
            (resultLabels[h.result] || h.result) + '</strong>' +
            (h.diff !== null && h.diff !== undefined ? ' (' + h.diff + '%)' : '') +
            '</span></div>';
    });
    wrap.innerHTML = html;
}

function siGetCookie(name) {
    var v = null;
    if (document.cookie) {
        document.cookie.split(';').forEach(function(c) {
            c = c.trim();
            if (c.indexOf(name + '=') === 0) v = decodeURIComponent(c.substring(name.length + 1));
        });
    }
    return v;
}

})();
