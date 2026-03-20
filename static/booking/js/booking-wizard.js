/**
 * VISKOVIC GROUP — Shared Booking Wizard JS
 * Functions shared across premium_booking and appointments booking pages.
 * Each page declares window.BOOKING_CONFIG with page-specific data.
 */

'use strict';

/* ── Theme persistence (anti-FOUC supplement) ── */
(function () {
    var saved = localStorage.getItem('booking-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.theme-btn').forEach(function (btn) {
            btn.classList.toggle('active', btn.dataset.theme === saved);
        });
    });
})();

/**
 * Switch theme and persist to localStorage.
 * Called by .theme-btn onclick="setTheme('light')" etc.
 */
function setTheme(name) {
    document.documentElement.setAttribute('data-theme', name);
    localStorage.setItem('booking-theme', name);
    document.querySelectorAll('.theme-btn').forEach(function (btn) {
        btn.classList.toggle('active', btn.dataset.theme === name);
    });
}

/* ── CSRF helper ── */
function getCookie(name) {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
        var c = cookies[i].trim();
        if (c.startsWith(name + '=')) {
            return decodeURIComponent(c.slice(name.length + 1));
        }
    }
    return null;
}

/* ── Step indicator ── */
/**
 * Update step indicator dots/lines.
 * @param {number} current  1-based current step
 * @param {number} total    total number of steps
 */
function updateStepIndicator(current, total) {
    for (var i = 1; i <= total; i++) {
        var dot = document.getElementById('si' + i);
        if (!dot) continue;
        dot.classList.remove('active', 'done');
        if (i < current) dot.classList.add('done');
        else if (i === current) dot.classList.add('active');

        var line = document.getElementById('siLine' + i);
        if (line) {
            line.style.background = i < current ? 'var(--green)' : 'var(--border)';
        }
    }
}

/* ── Step panel navigation ── */
/**
 * Show one step panel, hide all others.
 * @param {number} step     1-based step number to show
 * @param {Object} stepMap  mapping {stepNumber: elementId}, e.g. {1:'stepDate', 2:'stepTime'}
 */
function showStep(step, stepMap) {
    Object.values(stepMap).forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.classList.remove('active');
    });
    var target = document.getElementById(stepMap[step]);
    if (target) target.classList.add('active');
}

/* ── Calendar rendering ── */
var _currentDate = new Date();

/**
 * Render a month calendar into a grid element.
 * @param {Object} opts
 *   gridId       {string}   id of .days-grid element
 *   displayId    {string}   id of element showing "Month YYYY"
 *   selectedDate {string}   currently selected date YYYY-MM-DD (or '')
 *   unavailable  {Array}    list of YYYY-MM-DD strings that are unavailable
 *   onSelect     {Function} callback(dateStr) when user picks a date
 *   minDate      {Date}     earliest selectable date (default: today)
 */
function renderCalendar(opts) {
    var grid     = document.getElementById(opts.gridId);
    var display  = document.getElementById(opts.displayId);
    if (!grid) return;

    var year  = _currentDate.getFullYear();
    var month = _currentDate.getMonth();
    var today = new Date(); today.setHours(0,0,0,0);
    var minDate = opts.minDate || today;

    var monthNames = [
        'Januar','Februar','März','April','Mai','Juni',
        'Juli','August','September','Oktober','November','Dezember'
    ];
    if (display) display.textContent = monthNames[month] + ' ' + year;

    var firstDay = new Date(year, month, 1).getDay();
    firstDay = (firstDay + 6) % 7; // Mon=0
    var daysInMonth = new Date(year, month + 1, 0).getDate();

    var html = '';
    for (var i = 0; i < firstDay; i++) html += '<div class="day empty"></div>';

    for (var d = 1; d <= daysInMonth; d++) {
        var dateStr = year + '-' + String(month+1).padStart(2,'0') + '-' + String(d).padStart(2,'0');
        var thisDate = new Date(year, month, d);
        var cls = 'day';

        if (thisDate < minDate)                                   cls += ' disabled';
        else if (opts.unavailable && opts.unavailable.indexOf(dateStr) >= 0) cls += ' disabled';
        else if (dateStr === opts.selectedDate)                   cls += ' selected';

        if (thisDate.toDateString() === today.toDateString()) cls += ' today';

        var onclick = cls.indexOf('disabled') >= 0
            ? ''
            : ' onclick="' + (opts.onSelect ? opts.onSelect.name + '(\'' + dateStr + '\')' : '') + '"';

        html += '<div class="' + cls + '"' + onclick + '>' + d + '</div>';
    }
    grid.innerHTML = html;
}

/**
 * Move calendar by offset months (-1 or +1).
 * Call renderCalendar() again after this.
 */
function changeMonth(offset, renderFn) {
    _currentDate.setMonth(_currentDate.getMonth() + offset);
    if (typeof renderFn === 'function') renderFn();
}
