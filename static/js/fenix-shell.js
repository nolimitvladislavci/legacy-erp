/* ═══════════════════════════════════════════════════════════════════════════
   FENIX GLOBAL SHELL v1.0 — Panel Management, Swipe, Auto-Hide
   ═══════════════════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    // ── PANEL STATE ──────────────────────────────────────────────────────
    var shell = {
        el: null,
        left: null,
        right: null,
        top: null,
        bottom: null,
        center: null,
        overlay: null,
        isMobile: false,

        init: function() {
            // Support both new .shell and legacy .app-layout containers
            this.el      = document.querySelector('.shell') || document.querySelector('.app-layout');
            this.left    = document.querySelector('.shell-left') || document.querySelector('.sidebar');
            this.right   = document.querySelector('.shell-right') || document.getElementById('shellRight');
            this.top     = document.querySelector('.shell-top') || document.querySelector('.topbar');
            this.bottom  = document.querySelector('.shell-bottom') || document.querySelector('.bottom-tabs');
            this.center  = document.querySelector('.shell-center') || document.querySelector('.content');
            this.overlay = document.querySelector('.shell-overlay') || document.querySelector('.sidebar-overlay');

            if (!this.el) return; // No layout container found

            this.isMobile = window.innerWidth <= 768;
            this._bindResize();
            this._bindOverlay();
            this._bindSwipe();
            this._bindKeyboard();
            this._setModeFromPath();
            this._highlightActiveNav();
            this._initSyncStatus();
        },

        // ── LEFT PANEL ──────────────────────────────────────────────────
        openLeft: function() {
            if (!this.left) return;
            this.left.classList.add('open');
            this._showOverlay();
            // Sync legacy sidebar state
            document.body.classList.add('sidebar-open');
        },

        closeLeft: function() {
            if (!this.left) return;
            this.left.classList.remove('open');
            this._hideOverlay();
            document.body.classList.remove('sidebar-open');
        },

        toggleLeft: function() {
            if (this.left && this.left.classList.contains('open')) {
                this.closeLeft();
            } else {
                this.closeRight();
                this.openLeft();
            }
        },

        // ── RIGHT PANEL ─────────────────────────────────────────────────
        openRight: function(contentHtml) {
            if (!this.right) return;
            this.right.classList.remove('collapsed');
            this.right.classList.add('open');
            if (contentHtml) {
                var content = this.right.querySelector('.shell-right-content');
                if (content) content.innerHTML = contentHtml;
            }
            if (this.isMobile) this._showOverlay();
        },

        closeRight: function() {
            if (!this.right) return;
            this.right.classList.remove('open');
            if (!this.isMobile) this.right.classList.add('collapsed');
            if (this.isMobile) this._hideOverlay();
        },

        toggleRight: function() {
            if (this.right && this.right.classList.contains('open')) {
                this.closeRight();
            } else {
                this.closeLeft();
                this.openRight();
            }
        },

        // ── SHELL MODES ─────────────────────────────────────────────────
        setMode: function(mode) {
            if (!this.el) return;
            // Support both data-mode (new) and data-shell-mode (legacy)
            this.el.setAttribute('data-mode', mode || 'default');
            this.el.setAttribute('data-shell-mode', mode || 'default');
        },

        // Auto-detect mode based on URL path
        _setModeFromPath: function() {
            var path = window.location.pathname;

            // POS terminal = fullscreen
            if (/\/pos\/(quick|joker|terminal|kiosk|field)/.test(path)) {
                this.setMode('fullscreen');
                return;
            }

            // POS dashboard = focus (no right panel)
            if (/\/pos\//.test(path)) {
                this.setMode('focus');
                return;
            }

            // Forms = focus
            if (/\/(create|edit|new|form|wizard)/.test(path)) {
                this.setMode('focus');
                return;
            }

            // Default
            this.setMode('default');
        },

        // ── ACTIVE NAV HIGHLIGHTING ─────────────────────────────────────
        _highlightActiveNav: function() {
            if (!this.left) return;
            var path = window.location.pathname;
            var items = this.left.querySelectorAll('.shell-nav-item');
            items.forEach(function(item) {
                var href = item.getAttribute('href');
                if (!href) return;
                if (path.startsWith(href) && href.length > 4) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
        },

        // ── OVERLAY ─────────────────────────────────────────────────────
        _showOverlay: function() {
            if (this.overlay) this.overlay.classList.add('active');
        },

        _hideOverlay: function() {
            if (this.overlay) this.overlay.classList.remove('active');
        },

        _bindOverlay: function() {
            var self = this;
            if (this.overlay) {
                this.overlay.addEventListener('click', function() {
                    self.closeLeft();
                    self.closeRight();
                });
            }
        },

        // ── RESIZE ──────────────────────────────────────────────────────
        _bindResize: function() {
            var self = this;
            var resizeTimer;
            window.addEventListener('resize', function() {
                clearTimeout(resizeTimer);
                resizeTimer = setTimeout(function() {
                    var wasMobile = self.isMobile;
                    self.isMobile = window.innerWidth <= 768;
                    if (wasMobile !== self.isMobile) {
                        self.closeLeft();
                        self.closeRight();
                    }
                }, 150);
            });
        },

        // ── SWIPE GESTURES ──────────────────────────────────────────────
        _bindSwipe: function() {
            var self = this;
            var startX = 0;
            var startY = 0;
            var tracking = false;
            var THRESHOLD = 60;

            document.addEventListener('touchstart', function(e) {
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
                tracking = true;
            }, {passive: true});

            document.addEventListener('touchend', function(e) {
                if (!tracking) return;
                tracking = false;

                var endX = e.changedTouches[0].clientX;
                var endY = e.changedTouches[0].clientY;
                var dx = endX - startX;
                var dy = endY - startY;

                // Only horizontal swipes (dx > dy)
                if (Math.abs(dx) < THRESHOLD || Math.abs(dx) < Math.abs(dy)) return;

                if (dx > 0) {
                    // Swipe right → open left (only from left edge)
                    if (startX < 30 && !self.left.classList.contains('open')) {
                        self.openLeft();
                    }
                    // Swipe right while right is open → close right
                    else if (self.right && self.right.classList.contains('open')) {
                        self.closeRight();
                    }
                } else {
                    // Swipe left → open right (only from right edge)
                    if (startX > window.innerWidth - 30 && self.right && !self.right.classList.contains('open')) {
                        self.openRight();
                    }
                    // Swipe left while left is open → close left
                    else if (self.left && self.left.classList.contains('open')) {
                        self.closeLeft();
                    }
                }
            }, {passive: true});
        },

        // ── KEYBOARD SHORTCUTS ──────────────────────────────────────────
        _bindKeyboard: function() {
            var self = this;
            document.addEventListener('keydown', function(e) {
                // Escape → close all panels
                if (e.key === 'Escape') {
                    self.closeLeft();
                    self.closeRight();
                }

                // Ctrl+B → toggle left
                if (e.ctrlKey && e.key === 'b') {
                    e.preventDefault();
                    self.toggleLeft();
                }

                // Ctrl+. → toggle right
                if (e.ctrlKey && e.key === '.') {
                    e.preventDefault();
                    self.toggleRight();
                }
            });
        },

        // ── SYNC STATUS ─────────────────────────────────────────────────
        _initSyncStatus: function() {
            var dot = document.querySelector('.shell-status-dot');
            if (!dot) return;

            function updateStatus() {
                if (navigator.onLine) {
                    dot.className = 'shell-status-dot online';
                } else {
                    dot.className = 'shell-status-dot offline';
                }
            }

            updateStatus();
            window.addEventListener('online', updateStatus);
            window.addEventListener('offline', updateStatus);
        }
    };

    // ── PUBLIC API ───────────────────────────────────────────────────────
    window.FenixShell = shell;

    // Global shortcuts for templates
    window.openShellLeft  = function() { shell.openLeft(); };
    window.closeShellLeft = function() { shell.closeLeft(); };
    window.toggleShellLeft = function() { shell.toggleLeft(); };
    window.openShellRight = function(html) { shell.openRight(html); };
    window.closeShellRight = function() { shell.closeRight(); };
    window.toggleShellRight = function() { shell.toggleRight(); };
    window.setShellMode = function(m) { shell.setMode(m); };

    // Backward compatibility with old sidebar functions
    window.openSidebar  = function() { shell.openLeft(); };
    window.closeSidebar = function() { shell.closeLeft(); };

    // ── INIT ─────────────────────────────────────────────────────────────
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { shell.init(); });
    } else {
        shell.init();
    }

})();
