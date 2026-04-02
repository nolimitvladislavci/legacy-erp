"""
camera_btn — Template tag za inline kameru uz input polja

Primjer korištenja u template-u:
  {% load camera_tags %}

  <!-- Uz OIB polje: -->
  {% camera_btn field_id="id_oib" doc_type="id_card" label="Skeniraj osobnu" %}

  <!-- Uz sliku psa u azilu: -->
  {% camera_btn field_id="id_fotografija" doc_type="azil_zivotinja" label="Fotografiraj životinju" %}

  <!-- Uz fakturu/dokument: -->
  {% camera_btn field_id="id_dokument" doc_type="invoice" label="Skeniraj fakturu" %}
  
  <!-- Učitaj iz arhive (bez kamere): -->
  {% archive_btn field_id="id_fotografija" label="Učitaj iz arhive" %}

Parametri:
  field_id  — HTML id input polja koje se popunjava
  doc_type  — tip dokumenta za FenixScan AI (id_card|invoice|general|azil_zivotinja|golub)
  label     — tekst gumba (default: "Skeniraj")
  size      — "sm" | "md" (default: "sm")
"""
from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def camera_btn(field_id='', doc_type='general', label='Skeniraj', size='sm'):
    """
    Inline kamera gumb uz input polje.
    Otvara FenixScan modal i po završetku popunjava ciljno polje.
    """
    btn_class = 'btn btn-sm btn-outline-info' if size == 'sm' else 'btn btn-outline-info'
    btn_id = f'cam-btn-{field_id}'

    return format_html(
        '''<button type="button"
            id="{btn_id}"
            class="{btn_class}"
            style="white-space:nowrap"
            title="Fotografiraj ili učitaj dokument — AI automatski prepoznaje podatke"
            onclick="fenixScanInline('{field_id}', '{doc_type}', '{btn_id}')">
            <i class="fas fa-camera me-1"></i>{label}
        </button>
        <script>
        if(!window._fenixScanInlineLoaded) {{
            window._fenixScanInlineLoaded = true;
            window.fenixScanInline = function(fieldId, docType, btnId) {{
                var btn = document.getElementById(btnId);
                if(btn) {{ btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Skenira...'; }}
                // Koristi postojeći FenixScan ako je dostupan
                if(window.FenixScan && window.FenixScan.openForField) {{
                    FenixScan.openForField(fieldId, docType, function() {{
                        if(btn) {{ btn.disabled = false; btn.innerHTML = '<i class="fas fa-camera me-1"></i>' + btn.dataset.label; }}
                    }});
                }} else {{
                    // Fallback: file input trigger
                    var input = document.getElementById(fieldId);
                    if(input && input.type === 'file') {{
                        input.click();
                    }} else {{
                        // Otvori globalni FAB scan
                        var fab = document.getElementById('fenix-smart-fab');
                        if(fab) fab.click();
                    }}
                    if(btn) {{ btn.disabled = false; btn.innerHTML = '<i class="fas fa-camera me-1"></i>' + (btn.dataset.label || 'Skeniraj'); }}
                }}
            }};
        }}
        document.getElementById('{btn_id}').dataset.label = '{label}';
        </script>''',
        btn_id=btn_id,
        btn_class=btn_class,
        field_id=field_id,
        doc_type=doc_type,
        label=label
    )


@register.simple_tag
def archive_btn(field_id='', label='Učitaj iz arhive', size='sm'):
    """
    Gumb za učitavanje dokumenta iz arhive (bez kamere).
    Link na /documents/arhiva/ s povratkom na trenutnu stranicu.
    """
    btn_class = 'btn btn-sm btn-outline-secondary' if size == 'sm' else 'btn btn-outline-secondary'

    return format_html(
        '''<button type="button"
            class="{btn_class}"
            style="white-space:nowrap"
            title="Odaberi dokument iz arhive"
            onclick="fenixArchivePick('{field_id}')">
            <i class="fas fa-folder-open me-1"></i>{label}
        </button>
        <script>
        if(!window._fenixArchiveLoaded) {{
            window._fenixArchiveLoaded = true;
            window.fenixArchivePick = function(fieldId) {{
                // Otvori arhivu u popup prozoru — odabrani dokument se vraća u polje
                var w = window.open(
                    '/hr/documents/arhiva/?pick=1&field=' + fieldId,
                    'fenix_archive',
                    'width=900,height=600,scrollbars=yes'
                );
                // Slušaj poruku iz arhive kad korisnik odabere dokument
                window.addEventListener('message', function onArchivePick(e) {{
                    if(e.data && e.data.type === 'fenix_archive_pick' && e.data.field === fieldId) {{
                        var input = document.getElementById(fieldId);
                        if(input) {{
                            input.value = e.data.value || '';
                            input.dispatchEvent(new Event('change', {{bubbles: true}}));
                        }}
                        window.removeEventListener('message', onArchivePick);
                        if(w && !w.closed) w.close();
                    }}
                }});
            }};
        }}
        </script>''',
        btn_class=btn_class,
        field_id=field_id,
        label=label
    )


@register.inclusion_tag('core/partials/camera_input_group.html')
def camera_input_group(field, doc_type='general', show_archive=True):
    """
    Kompletan input group: [input field] [📷 Skeniraj] [📁 Arhiva]
    
    Primjer:
      {% camera_input_group form.oib doc_type="id_card" %}
      {% camera_input_group form.fotografija doc_type="azil_zivotinja" show_archive=True %}
    """
    return {
        'field': field,
        'doc_type': doc_type,
        'show_archive': show_archive,
        'field_id': f'id_{field.html_name}' if hasattr(field, 'html_name') else 'field',
    }
