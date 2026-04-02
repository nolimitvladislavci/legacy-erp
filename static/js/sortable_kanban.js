/**
 * BORG Faza 2 v2 — Sortable Kanban + Stale Detection + Board Polling
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Drag-and-drop between kanban columns with FSM validation.
 * - expected_status: prevents stale card moves (Dron #3)
 * - board_version polling: lightweight 30s "has changes?" check
 * - Rejected cards animate back with toast error
 *
 * Usage:
 *   add class="kanban-sortable" and data-status="STATUS" to each column body
 *   Cards need: data-card-id, data-model, data-status attributes
 *   Optional: data-poll="true" on kanban-wrap to enable auto-refresh
 */
(function () {
    'use strict';

    // ── CSRF ──────────────────────────────────────────────────────
    function getCSRF() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        var c = document.cookie.match(/csrftoken=([^;]+)/);
        return c ? c[1] : '';
    }

    // ── Toast ─────────────────────────────────────────────────────
    function showToast(msg, type) {
        if (typeof fenixToast === 'function') { fenixToast(msg, type); return; }
        if (typeof toast === 'function') { toast(msg, type); return; }
        var container = document.getElementById('tc') || document.body;
        var t = document.createElement('div');
        t.style.cssText = 'position:fixed;top:24px;right:24px;z-index:9999;padding:14px 20px;border-radius:10px;font-size:.88rem;font-weight:500;min-width:280px;max-width:420px;box-shadow:0 8px 32px rgba(0,0,0,.4);animation:tIn .3s ease;';
        t.style.background = type === 'error' ? '#450a0a' : type === 'warning' ? '#422006' : '#064e3b';
        t.style.color = type === 'error' ? '#fca5a5' : type === 'warning' ? '#fbbf24' : '#6ee7b7';
        t.textContent = msg;
        container.appendChild(t);
        setTimeout(function() { t.remove(); }, 4000);
    }

    // ── Column counter update ─────────────────────────────────────
    function updateColumnCounts() {
        document.querySelectorAll('.kanban-col, .iv-col').forEach(function (col) {
            var body = col.querySelector('.kanban-sortable, .kanban-cards, .iv-col-body');
            var badge = col.querySelector('.kanban-badge, .iv-col-count');
            if (body && badge) {
                var cards = body.querySelectorAll('.kanban-card, .iv-card');
                badge.textContent = cards.length;
            }
        });
    }

    // ── Card move via BORG API ────────────────────────────────────
    function moveCard(cardEl, fromCol, toCol, oldIndex) {
        var cardId = cardEl.dataset.cardId;
        var model = cardEl.dataset.model;
        var newStatus = toCol.dataset.status;
        var expectedStatus = cardEl.dataset.status || ''; // Dron #3: stale detection

        if (!cardId || !model || !newStatus) return;

        // Disable card during transition
        cardEl.style.opacity = '0.6';
        cardEl.style.pointerEvents = 'none';

        fetch('/api/card/move/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRF(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: model,
                pk: cardId,
                new_status: newStatus,
                expected_status: expectedStatus,
            }),
        })
        .then(function (r) { return r.json().then(function(d) { return {ok: r.ok, data: d}; }); })
        .then(function (result) {
            cardEl.style.opacity = '1';
            cardEl.style.pointerEvents = '';

            if (!result.data.ok) {
                // FSM rejected or stale — animate card back
                var refChild = fromCol.children[oldIndex] || null;
                fromCol.insertBefore(cardEl, refChild);

                if (result.data.stale) {
                    showToast(result.data.error || 'Kartica je promijenjena. Osvježite.', 'warning');
                    // Auto-refresh after stale detection
                    setTimeout(function() { location.reload(); }, 2000);
                } else {
                    showToast(result.data.error || 'Premještanje odbijeno', 'error');
                }
            } else {
                // Success — update card's data-status attribute
                cardEl.dataset.status = newStatus;
                showToast(result.data.message || 'Premješteno', 'success');
                updateColumnCounts();
                // Update last known version time
                _lastCheck = new Date().toISOString();
            }
        })
        .catch(function () {
            cardEl.style.opacity = '1';
            cardEl.style.pointerEvents = '';
            var refChild = fromCol.children[oldIndex] || null;
            fromCol.insertBefore(cardEl, refChild);
            showToast('Mrežna greška — pokušajte ponovo', 'error');
        });
    }

    // ── Init Sortable on all columns ──────────────────────────────
    function initSortableKanban() {
        var cols = document.querySelectorAll('.kanban-sortable');
        if (!cols.length) return;

        cols.forEach(function (col) {
            // Skip if already initialized
            if (col._sortableInit) return;
            col._sortableInit = true;

            new Sortable(col, {
                group: 'kanban',
                animation: 200,
                ghostClass: 'kanban-ghost',
                chosenClass: 'kanban-chosen',
                dragClass: 'kanban-drag',
                easing: 'cubic-bezier(0.25, 1, 0.5, 1)',
                delay: 100,
                delayOnTouchOnly: true,
                onEnd: function (evt) {
                    if (evt.from === evt.to) return;
                    moveCard(evt.item, evt.from, evt.to, evt.oldIndex);
                },
            });
        });
    }

    // ── Board Version Polling (Dron #3) ───────────────────────────
    var _lastCheck = new Date().toISOString();
    var _pollInterval = null;
    var _refreshBanner = null;

    function startBoardPolling(intervalMs) {
        if (_pollInterval) return;
        intervalMs = intervalMs || 30000;

        _pollInterval = setInterval(function() {
            fetch('/api/card/version/?since=' + encodeURIComponent(_lastCheck), {
                headers: { 'X-CSRFToken': getCSRF() },
                credentials: 'same-origin',
            })
            .then(function(r) { return r.json(); })
            .then(function(d) {
                if (d.has_changes && d.count > 0) {
                    showRefreshBanner(d.count);
                }
                _lastCheck = d.latest || _lastCheck;
            })
            .catch(function() { /* silent — network issue, retry next cycle */ });
        }, intervalMs);
    }

    function showRefreshBanner(count) {
        if (_refreshBanner) return; // Already showing

        _refreshBanner = document.createElement('div');
        _refreshBanner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9998;background:linear-gradient(135deg,#1e3a5f,#0f172a);border-bottom:2px solid var(--gold,#c9a84c);padding:10px 20px;display:flex;align-items:center;justify-content:center;gap:12px;font-size:.85rem;color:#e0e0e0;animation:slideDown .3s ease;';
        _refreshBanner.innerHTML =
            '<span style="color:var(--gold,#c9a84c);font-weight:700">⚡ ' + count + ' promjen' + (count === 1 ? 'a' : 'e') + ' na ploči</span>' +
            '<button onclick="location.reload()" style="background:var(--gold,#c9a84c);color:#0a0a0a;border:none;border-radius:6px;padding:6px 16px;font-size:.78rem;font-weight:700;cursor:pointer">Osvježi</button>' +
            '<button onclick="this.parentElement.remove();window._refreshBanner=null;" style="background:none;border:none;color:#6b7280;cursor:pointer;font-size:1.1rem;padding:4px 8px">✕</button>';

        document.body.prepend(_refreshBanner);
    }

    // ── HTMX event listeners (Dron #3) ────────────────────────────
    document.addEventListener('showFsmError', function(e) {
        showToast(e.detail || 'Greška pri premještanju', 'error');
    });

    document.addEventListener('refreshBoard', function() {
        showRefreshBanner(1);
    });

    // ── Init ──────────────────────────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initSortableKanban();
            // Auto-start polling if kanban-wrap has data-poll="true"
            var wrap = document.querySelector('[data-poll]');
            if (wrap) startBoardPolling(parseInt(wrap.dataset.poll) || 30000);
        });
    } else {
        initSortableKanban();
        var wrap = document.querySelector('[data-poll]');
        if (wrap) startBoardPolling(parseInt(wrap.dataset.poll) || 30000);
    }

    // Re-init after HTMX content swap
    document.addEventListener('htmx:afterSwap', initSortableKanban);

    // Public API
    window.BorgKanban = {
        refresh: function() { location.reload(); },
        startPolling: startBoardPolling,
        showToast: showToast,
    };
})();
