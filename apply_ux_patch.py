import re, shutil

TPL = '/var/www/fina-connect/invoicing/templates/invoicing/create.html'
with open(TPL) as f:
    c = f.read()

shutil.copy(TPL, TPL + '.bak_ux')
print(f"Backup: {TPL}.bak_ux")

BANNER = '''
{# ═══ LOCKED BANNER ═══ #}
{% if invoice.is_locked %}
<div class="alert d-flex align-items-start gap-3 mb-3" id="locked-banner" role="alert"
     style="border-left:4px solid #f59e0b;background:#fffbeb;border-radius:10px;padding:14px 18px;margin-bottom:20px">
  <div style="font-size:1.6rem;flex-shrink:0;line-height:1.1">🔒</div>
  <div style="flex:1">
    <div style="font-weight:700;color:#92400e;font-size:1rem;margin-bottom:4px">
      Račun je zaključan &mdash; samo za čitanje
    </div>
    <div style="font-size:.85rem;color:#78350f">
      {% if invoice.is_fiscalized %}
        Račun <strong>{{ invoice.number }}</strong> je fiskaliziran
        {% if invoice.jir %}— JIR: <code style="font-size:.78rem;background:#fef3c7;padding:1px 5px;border-radius:3px">{{ invoice.jir }}</code>{% endif %}
        i zakonski je nepromjenjiv (<strong>ZOR čl. 9</strong>).
        Za ispravak izaberite <strong>↩ Storno</strong> u desnom izborniku.
      {% elif invoice.synesis_id %}
        Račun je uvezen iz Synesis arhive — samo za čitanje.
      {% else %}
        Račun je administrativno zaključan.
      {% endif %}
    </div>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;align-items:center;font-size:.78rem;color:#92400e">
      {% if invoice.deletion_protected_until %}
      <span><i class="fas fa-shield-alt me-1"></i>Čuva se do: <strong>{{ invoice.deletion_protected_until|date:"d.m.Y" }}</strong></span>
      {% endif %}
      {% if invoice.fiscal_datetime %}
      <span><i class="fas fa-stamp me-1"></i>Fiskalizirano: {{ invoice.fiscal_datetime|date:"d.m.Y H:i" }}</span>
      {% endif %}
      {% if invoice.zki %}
      <span style="font-family:monospace;font-size:.72rem;opacity:.7">ZKI: {{ invoice.zki|truncatechars:20 }}</span>
      {% endif %}
    </div>
  </div>
</div>
{% endif %}
'''

ANCHOR = '<!-- AJAX Save Indicator -->'
if 'locked-banner' not in c:
    c = c.replace(ANCHOR, ANCHOR + '\n' + BANNER, 1)
    print("✅ PATCH 1 — locked banner ubačen")
else:
    print("ℹ️  PATCH 1 — banner već postoji")

OLD_FISCAL = '''            <a href="/invoicing/{{ invoice.pk }}/fiscalize/" class="btn-action btn-fiscal" id="fiscalBtn"
               {% if invoice.is_fiscalized %}style="background:#166534;opacity:0.7;pointer-events:none"{% endif %}>
              ⚡ {% if invoice.is_fiscalized %}Fiskalizirano ✓{% else %}Fiskaliziraj{% endif %}
            </a>'''

NEW_FISCAL = '''            {% if invoice.is_fiscalized %}
            <div class="btn-action btn-fiscal"
                 style="background:#166534;opacity:0.65;cursor:not-allowed;user-select:none"
                 title="Račun je već fiskaliziran — JIR: {{ invoice.jir|default:'dodijeljen' }}"
                 data-bs-toggle="tooltip" data-bs-placement="left">
              ✓ Fiskalizirano
            </div>
            {% else %}
            <a href="/invoicing/{{ invoice.pk }}/fiscalize/" class="btn-action btn-fiscal" id="fiscalBtn">
              ⚡ Fiskaliziraj
            </a>
            {% endif %}'''

if OLD_FISCAL in c:
    c = c.replace(OLD_FISCAL, NEW_FISCAL)
    print("✅ PATCH 2 — fiscalize gumb poboljšan")
else:
    print("⚠️  PATCH 2 — fiscalize gumb nije pronađen")

OLD_SAVE1 = '''            <button type="submit" name="action" value="save" class="btn-action btn-save">
              {% trans "💾 Spremi dokument" %}
            </button>'''

NEW_SAVE1 = '''            <button type="submit" name="action" value="save" class="btn-action btn-save"
              {% if invoice.is_locked %}
                disabled
                title="{% if invoice.is_fiscalized %}Fiskaliziran račun je zakonski nepromjenjiv (ZOR čl. 9) — koristite Storno za ispravak{% else %}Račun je zaključan{% endif %}"
                style="opacity:0.5;cursor:not-allowed"
              {% endif %}>
              {% trans "💾 Spremi dokument" %}
            </button>'''

if OLD_SAVE1 in c:
    c = c.replace(OLD_SAVE1, NEW_SAVE1)
    print("✅ PATCH 3a — Spremi dokument disabled kad locked")
else:
    print("⚠️  PATCH 3a — nije pronađen")

OLD_SAVE2 = '''        <button type="submit" name="action" value="save" class="btn-sticky-save green">
          💾 {% trans "Spremi" %}
        </button>'''

NEW_SAVE2 = '''        <button type="submit" name="action" value="save" class="btn-sticky-save green"
          {% if invoice.is_locked %}
            disabled
            title="{% if invoice.is_fiscalized %}Fiskaliziran — koristite Storno{% else %}Zaključano{% endif %}"
            style="opacity:0.5;cursor:not-allowed;background:#6b7280"
          {% endif %}>
          {% if invoice.is_locked %}🔒 Zaključano{% else %}💾 {% trans "Spremi" %}{% endif %}
        </button>'''

if OLD_SAVE2 in c:
    c = c.replace(OLD_SAVE2, NEW_SAVE2)
    print("✅ PATCH 3b — sticky Spremi disabled kad locked")
else:
    print("⚠️  PATCH 3b — nije pronađen")

LOCKED_JS = '''
{# ═══ LOCKED FORM JS ═══ #}
{% if invoice.is_locked %}
<script>
(function(){
  var REASON = '{% if invoice.is_fiscalized %}Račun je fiskaliziran i zakonski nepromjenjiv (ZOR čl. 9). Za ispravak koristite Storno.{% elif invoice.synesis_id %}Uvezeno iz Synesis arhive — samo za čitanje.{% else %}Račun je zaključan.{% endif %}';
  document.addEventListener('DOMContentLoaded', function(){
    var form = document.getElementById('invoiceForm');
    if(form){
      form.querySelectorAll('input:not([type=hidden]),select,textarea').forEach(function(el){
        el.disabled = true; el.style.cursor = 'not-allowed'; el.style.opacity = '0.7';
      });
      ['quickBarWrap','aiTextInput','aiParseBtn','articleSearch','aiThinking'].forEach(function(id){
        var el = document.getElementById(id); if(el) el.style.display = 'none';
      });
      var addBtn = form.querySelector('.btn-add-item'); if(addBtn) addBtn.style.display = 'none';
      var copyBtn = form.querySelector('.btn-copy-invoice'); if(copyBtn) copyBtn.style.display = 'none';
      form.querySelectorAll('.btn-del-item').forEach(function(b){ b.style.display='none'; });
    }
    document.querySelectorAll('[disabled]').forEach(function(el){
      if(!el.title) el.title = REASON; el.style.cursor = 'not-allowed';
    });
    if(typeof bootstrap !== 'undefined' && bootstrap.Tooltip){
      document.querySelectorAll('[data-bs-toggle="tooltip"],[title][disabled]').forEach(function(el){
        if(!el.getAttribute('data-bs-toggle')) el.setAttribute('data-bs-toggle','tooltip');
        try{ new bootstrap.Tooltip(el); }catch(e){}
      });
    }
    if(form){
      form.addEventListener('click', function(e){
        if(e.target.closest('a[href],button:not([disabled])')) return;
        var banner = document.getElementById('locked-banner'); if(!banner) return;
        banner.style.transition = 'box-shadow .15s';
        banner.style.boxShadow = '0 0 0 3px #f59e0b';
        setTimeout(function(){ banner.style.boxShadow = ''; }, 900);
      });
    }
    console.log('[FINA] Invoice locked — form disabled');
  });
})();
</script>
{% endif %}
'''

if 'LOCKED FORM JS' not in c:
    c = c.replace('{% endblock %}', LOCKED_JS + '\n{% endblock %}', 1)
    print("✅ PATCH 4 — JS form lock ubačen")
else:
    print("ℹ️  PATCH 4 — JS već postoji")

with open(TPL, 'w') as f:
    f.write(c)

print(f"\n✅ Gotovo! {TPL} ({len(c):,} chars)")
print("   ✓ Banner:", "DA" if "locked-banner" in c else "NE")
print("   ✓ Fiscal tooltip:", "DA" if "JIR: {{ invoice.jir" in c else "NE")
print("   ✓ Save disabled:", "DA" if "is_locked" in c and "disabled" in c else "NE")
print("   ✓ JS lock:", "DA" if "LOCKED FORM JS" in c else "NE")
