/**
 * FCWizard — Reusable step-by-step wizard framework for LIMIT Connect ERP
 * Usage:
 *   const wiz = new FCWizard({
 *     container: '#wizard-root',
 *     steps: [
 *       { id: 'client', title: 'Klijent', icon: '👤',
 *         validate: async (data) => { ... return {valid, message} },
 *         collectData: () => ({...}) },
 *       ...
 *     ],
 *     onComplete: (data) => { ... },
 *     onStepChange: (oldIdx, newIdx) => { ... },
 *     theme: 'dark'  // 'dark' (default) or 'light'
 *   });
 */
class FCWizard {
  constructor(opts) {
    this.container = typeof opts.container === 'string'
      ? document.querySelector(opts.container) : opts.container;
    this.steps = opts.steps || [];
    this.onComplete = opts.onComplete || (() => {});
    this.onStepChange = opts.onStepChange || (() => {});
    this.theme = opts.theme || 'dark';
    this.currentStep = 0;
    this.data = {};
    this._init();
  }

  _init() {
    this.container.classList.add('fcw-wizard', `fcw-theme-${this.theme}`);
    // Build progress bar
    this._buildProgress();
    // Build step panels wrapper
    this.panelsWrap = document.createElement('div');
    this.panelsWrap.className = 'fcw-panels-wrap';
    this.container.appendChild(this.panelsWrap);
    // Build navigation
    this._buildNav();
    // Show first step
    this._showStep(0);
    // Keyboard: Enter = next (except textarea)
    this.container.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && !e.target.classList.contains('fcw-no-enter')) {
        e.preventDefault();
        this.next();
      }
    });
  }

  _buildProgress() {
    this.progressBar = document.createElement('div');
    this.progressBar.className = 'fcw-progress';
    const inner = document.createElement('div');
    inner.className = 'fcw-progress-inner';
    this.steps.forEach((step, i) => {
      if (i > 0) {
        const line = document.createElement('div');
        line.className = 'fcw-progress-line';
        line.dataset.idx = i;
        inner.appendChild(line);
      }
      const circle = document.createElement('div');
      circle.className = 'fcw-progress-step';
      circle.dataset.idx = i;
      circle.innerHTML = `<div class="fcw-step-circle">${step.icon || (i + 1)}</div>
        <div class="fcw-step-label">${step.title}</div>`;
      circle.addEventListener('click', () => this._clickStep(i));
      inner.appendChild(circle);
    });
    this.progressBar.appendChild(inner);
    this.container.appendChild(this.progressBar);
  }

  _buildNav() {
    this.navBar = document.createElement('div');
    this.navBar.className = 'fcw-nav';
    this.navBar.innerHTML = `
      <button type="button" class="fcw-btn fcw-btn-back"><i class="fas fa-arrow-left"></i> Natrag</button>
      <span class="fcw-step-counter"></span>
      <button type="button" class="fcw-btn fcw-btn-next">Dalje <i class="fas fa-arrow-right"></i></button>`;
    this.container.appendChild(this.navBar);
    this.btnBack = this.navBar.querySelector('.fcw-btn-back');
    this.btnNext = this.navBar.querySelector('.fcw-btn-next');
    this.stepCounter = this.navBar.querySelector('.fcw-step-counter');
    this.btnBack.addEventListener('click', () => this.back());
    this.btnNext.addEventListener('click', () => this.next());
  }

  _showStep(idx) {
    // Hide all panels
    this.panelsWrap.querySelectorAll('.fcw-panel').forEach(p => {
      p.classList.remove('fcw-panel-active');
    });
    // Show target panel
    const panel = this.panelsWrap.querySelector(`[data-step="${idx}"]`);
    if (panel) {
      panel.classList.add('fcw-panel-active');
    }
    // Update progress
    this._updateProgress(idx);
    // Update nav
    this.btnBack.style.display = idx === 0 ? 'none' : '';
    if (idx === this.steps.length - 1) {
      this.btnNext.style.display = 'none';
    } else {
      this.btnNext.style.display = '';
      this.btnNext.innerHTML = 'Dalje <i class="fas fa-arrow-right"></i>';
    }
    this.stepCounter.textContent = `Korak ${idx + 1} od ${this.steps.length}`;
  }

  _updateProgress(activeIdx) {
    this.progressBar.querySelectorAll('.fcw-progress-step').forEach(el => {
      const i = parseInt(el.dataset.idx);
      el.classList.remove('fcw-step-active', 'fcw-step-completed', 'fcw-step-future');
      if (i < activeIdx) el.classList.add('fcw-step-completed');
      else if (i === activeIdx) el.classList.add('fcw-step-active');
      else el.classList.add('fcw-step-future');
    });
    this.progressBar.querySelectorAll('.fcw-progress-line').forEach(el => {
      const i = parseInt(el.dataset.idx);
      el.classList.remove('fcw-line-completed', 'fcw-line-active');
      if (i <= activeIdx) el.classList.add('fcw-line-completed');
    });
  }

  _clickStep(idx) {
    // Can only click on completed steps to go back
    if (idx < this.currentStep) {
      this._collectCurrent();
      const old = this.currentStep;
      this.currentStep = idx;
      this._showStep(idx);
      this.onStepChange(old, idx);
    }
  }

  _collectCurrent() {
    const step = this.steps[this.currentStep];
    if (step && typeof step.collectData === 'function') {
      const stepData = step.collectData();
      Object.assign(this.data, stepData);
    }
  }

  async next() {
    const step = this.steps[this.currentStep];
    // Collect data first
    this._collectCurrent();
    // Validate
    if (typeof step.validate === 'function') {
      const result = await step.validate(this.data);
      if (result && !result.valid) {
        this._showError(result.message || 'Molimo ispunite sva obavezna polja.');
        return false;
      }
    }
    this._clearError();
    if (this.currentStep < this.steps.length - 1) {
      const old = this.currentStep;
      this.currentStep++;
      this._showStep(this.currentStep);
      this.onStepChange(old, this.currentStep);
      // Call onEnter if defined
      const nextStep = this.steps[this.currentStep];
      if (typeof nextStep.onEnter === 'function') {
        nextStep.onEnter(this.data);
      }
      return true;
    }
    return false;
  }

  back() {
    if (this.currentStep > 0) {
      this._collectCurrent();
      this._clearError();
      const old = this.currentStep;
      this.currentStep--;
      this._showStep(this.currentStep);
      this.onStepChange(old, this.currentStep);
    }
  }

  goTo(idx) {
    if (idx >= 0 && idx < this.steps.length) {
      this._collectCurrent();
      this._clearError();
      const old = this.currentStep;
      this.currentStep = idx;
      this._showStep(idx);
      this.onStepChange(old, idx);
    }
  }

  _showError(msg) {
    this._clearError();
    const errDiv = document.createElement('div');
    errDiv.className = 'fcw-error';
    errDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${msg}`;
    this.navBar.insertAdjacentElement('beforebegin', errDiv);
  }

  _clearError() {
    const existing = this.container.querySelector('.fcw-error');
    if (existing) existing.remove();
  }

  /** Register a panel element for a step */
  addPanel(idx, element) {
    element.classList.add('fcw-panel');
    element.dataset.step = idx;
    this.panelsWrap.appendChild(element);
  }

  /** Get all collected data */
  getData() {
    this._collectCurrent();
    return { ...this.data };
  }
}
