/**
 * BORG Faza 2 — Sortable Kanban
 * Enables drag-and-drop between kanban columns.
 * FSM validates server-side; rejected cards animate back.
 *
 * Usage: add class="kanban-sortable" and data-status="STATUS" to each column body.
 * Cards need data-card-id and data-model attributes.
 */
(function () {
    'use strict';

    function getCSRF() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        const c = document.cookie.match(/csrftoken=([^;]+)/);
        return c ? c[1] : '';
    }

    function showToast(msg, type) {
        // Try fenixToast first (interventions), then generic toast (burza)
        if (typeof fenixToast === 'function') { fenixToast(msg, type); return; }
        if (typeof toast === 'function') { toast(msg, type); return; }
        // Fallback: create temporary toast
        const container = document.getElementById('tc') || document.body;
        const t = document.createElement('div');
        t.style.cssText = 'position:fixed;top:24px;right:24px;z-index:9999;padding:14px 20px;border-radius:10px;font-size:.88rem;font-weight:500;min-width:280px;box-shadow:0 8px 32px rgba(0,0,0,.4);animation:tIn .3s ease;';
        t.style.background = type === 'error' ? '#450a0a' : '#064e3b';
        t.style.color = type === 'error' ? '#fca5a5' : '#6ee7b7';
        t.textContent = msg;
        container.appendChild(t);
        setTimeout(() => t.remove(), 4000);
    }

    function initSortableKanban() {
        const cols = document.querySelectorAll('.kanban-sortable');
        if (!cols.length) return;

        cols.forEach(function (col) {
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
                    // Same column — just reorder, no status change
                    if (evt.from === evt.to) return;

                    var cardEl = evt.item;
                    var cardId = cardEl.dataset.cardId;
                    var model = cardEl.dataset.model;
                    var newStatus = evt.to.dataset.status;

                    if (!cardId || !model || !newStatus) return;

                    // Optimistic UI — card is already moved by Sortable
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
                        }),
                    })
                    .then(function (r) { return r.json(); })
                    .then(function (d) {
                        if (!d.ok) {
                            // FSM rejected — animate card back to original column
                            var refChild = evt.from.children[evt.oldIndex] || null;
                            evt.from.insertBefore(cardEl, refChild);
                            showToast(d.error || 'Premještanje odbijeno', 'error');
                        } else {
                            showToast(d.message || 'Premješteno', 'success');
                            // Update column counters if present
                            updateColumnCounts();
                        }
                    })
                    .catch(function () {
                        // Network error — put card back
                        var refChild = evt.from.children[evt.oldIndex] || null;
                        evt.from.insertBefore(cardEl, refChild);
                        showToast('Mrežna greška', 'error');
                    });
                },
            });
        });
    }

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

    // Init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSortableKanban);
    } else {
        initSortableKanban();
    }

    // Re-init after HTMX content swap
    document.addEventListener('htmx:afterSwap', initSortableKanban);
})();
