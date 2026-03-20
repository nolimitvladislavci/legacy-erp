/** Extracted from goods_receipt_form.html — no Django template vars */
// ── Row template ──────────────────────────────────────────────────────────────
let grRowIdx = 0;

function grAddRow(art) {
  grRowIdx++;
  const name   = art ? art.name : '';
  const itemId = art ? art.id   : '';
  const pp     = art ? parseFloat(art.purchase_price || 0).toFixed(4) : '0.0000';
  const tax    = art ? parseFloat(art.tax_rate || 25)  : 25;

  const tr = document.createElement('tr');
  tr.className = 'gr-row';
  tr.innerHTML = `
    <td>
      <input type="text"   class="form-control form-control-sm gr-art-name"
             value="${grEsc(name)}" placeholder="Naziv artikla" readonly
             style="background:#0f172a;border-color:#334155;color:#e2e8f0;min-width:160px">
      <input type="hidden" name="item_id[]" class="gr-item-id" value="${grEsc(itemId)}">
    </td>
    <td><input type="number" name="quantity[]" class="form-control form-control-sm gr-qty" value="1" step="0.001" min="0.001" style="background:#0f172a;border-color:#334155;color:#e2e8f0;width:80px"></td>
    <td><input type="number" name="purchase_price[]" class="form-control form-control-sm gr-pp" value="${pp}" step="0.0001" min="0" style="background:#0f172a;border-color:#334155;color:#e2e8f0;width:110px"></td>
    <td><input type="number" name="dependent_costs[]" class="form-control form-control-sm gr-dc" value="0" step="0.0001" min="0" style="background:#0f172a;border-color:#334155;color:#e2e8f0;width:110px"></td>
    <td class="gr-cp" style="color:var(--gold);font-family:monospace">0.0000</td>
    <td><input type="number" name="margin_percent[]" class="form-control form-control-sm gr-margin" value="30" step="0.01" min="0" style="background:#0f172a;border-color:#334155;color:#e2e8f0;width:80px"></td>
    <td class="gr-sn" style="color:#3b82f6;font-family:monospace">0.0000</td>
    <td><input type="number" name="tax_rate[]" class="form-control form-control-sm gr-tax" value="${tax}" step="0.01" min="0" style="background:#0f172a;border-color:#334155;color:#e2e8f0;width:70px"></td>
    <td class="gr-vat" style="color:#3b82f6;font-family:monospace">0.0000</td>
    <td class="gr-mpc" style="color:var(--gold);font-family:monospace;font-weight:700">0.0000</td>
    <td class="gr-tot" style="font-family:monospace;font-weight:700">0.00</td>
    <td><button type="button" class="btn btn-sm btn-outline-danger" onclick="grRemoveRow(this)"><i class="fas fa-times"></i></button></td>
  `;
  document.getElementById('grBody').appendChild(tr);
  grBindRow(tr);
  grCalcRow(tr);
}

function grBindRow(tr) {
  tr.querySelectorAll('.gr-qty,.gr-pp,.gr-dc,.gr-margin,.gr-tax').forEach(inp => {
    inp.addEventListener('input', () => grCalcRow(tr));
  });
}

function grCalcRow(tr) {
  const qty    = parseFloat(tr.querySelector('.gr-qty').value)    || 0;
  const pp     = parseFloat(tr.querySelector('.gr-pp').value)     || 0;
  const dc     = parseFloat(tr.querySelector('.gr-dc').value)     || 0;
  const margin = parseFloat(tr.querySelector('.gr-margin').value) || 0;
  const tax    = parseFloat(tr.querySelector('.gr-tax').value)    || 0;

  const cp  = pp + dc;
  const ma  = cp * margin / 100;
  const sn  = cp + ma;
  const va  = sn * tax / 100;
  const sg  = sn + va;
  const tot = sg * qty;

  tr.querySelector('.gr-cp').textContent  = cp.toFixed(4);
  tr.querySelector('.gr-sn').textContent  = sn.toFixed(4);
  tr.querySelector('.gr-vat').textContent = va.toFixed(4);
  tr.querySelector('.gr-mpc').textContent = sg.toFixed(4);
  tr.querySelector('.gr-tot').textContent = tot.toFixed(2);
  grCalcTotals();
}

function grCalcTotals() {
  let total = 0;
  document.querySelectorAll('.gr-row').forEach(tr => {
    total += parseFloat(tr.querySelector('.gr-tot').textContent) || 0;
  });
  document.getElementById('grTotMPC').textContent = total.toFixed(2) + ' EUR';
}

function grRemoveRow(btn) {
  btn.closest('tr').remove();
  grCalcTotals();
}

function grEsc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}

// ── Article search ─────────────────────────────────────────────────────────────
let grT;
document.getElementById('grArtSearch').addEventListener('input', function() {
  clearTimeout(grT);
  const q = this.value.trim();
  const dd = document.getElementById('grArtResults');
  if (q.length < 1) { dd.style.display = 'none'; return; }
  grT = setTimeout(() => {
    fetch('/pos/api/articles/search/?q=' + encodeURIComponent(q))
      .then(r => r.json())
      .then(data => {
        dd.innerHTML = '';
        if (!data.articles || !data.articles.length) {
          dd.innerHTML = '<div style="padding:10px;color:#64748b;font-size:.8rem">Nema rezultata</div>';
          dd.style.display = 'block';
          return;
        }
        data.articles.forEach(a => {
          const div = document.createElement('div');
          div.style.cssText = 'padding:8px 12px;cursor:pointer;border-bottom:1px solid #1e293b;font-size:.8rem';
          div.innerHTML = `<strong style="color:#e2e8f0">${grEsc(a.name)}</strong>
            <span style="color:#64748b;margin-left:6px">${grEsc(a.sku)}</span>
            <span style="color:#94a3b8;float:right">${parseFloat(a.stock_qty).toFixed(2)} ${grEsc(a.unit||'')}</span>
            <br><small style="color:var(--gold)">Nab: ${parseFloat(a.purchase_price).toFixed(2)} EUR · PDV: ${a.tax_rate}%</small>`;
          div.addEventListener('mouseenter', () => div.style.background = 'rgba(201,168,76,.12)');
          div.addEventListener('mouseleave', () => div.style.background = '');
          div.addEventListener('click', () => {
            grAddRow(a);
            document.getElementById('grArtSearch').value = '';
            dd.style.display = 'none';
          });
          dd.appendChild(div);
        });
        dd.style.display = 'block';
      })
      .catch(() => { dd.style.display = 'none'; });
  }, 250);
});

document.addEventListener('click', e => {
  if (!e.target.closest('#grArtSearch') && !e.target.closest('#grArtResults'))
    document.getElementById('grArtResults').style.display = 'none';
});
