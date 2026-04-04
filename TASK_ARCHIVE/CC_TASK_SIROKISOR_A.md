# CC_TASK_SIROKISOR_A — QR kodovi + Narudžba flow
**Dodjeljeno:** CC Code (računalo)
**Deadline:** ASAP
**Ne dira:** synesis_compare.py, konto/, kindergarten/

---

## A1 — QR kod generiranje za 20 stolova

### Što treba:
Za svaki TableQR generirati PNG sliku s QR kodom koji vodi na digitalni menu.

### URL format:
```
https://limit-connect.com/gastro-menu/menu/korpas-doo-siroki-sor/?table={table_number}
```

### Skripta:
Kreirati `scripts/generate_table_qr.py`:

```python
"""
Generira QR kod PNG za svaki TableQR Široki Šor.
Output: media/gastro/table_qr/
Koristi: qrcode library (pip install qrcode[pil])
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import sys; sys.path.insert(0, '/var/www/fina-connect')
django.setup()

import qrcode
from qrcode.image.styledpil import StyledPilImage
from PIL import Image, ImageDraw, ImageFont
from gastro_menu.models import TableQR, DigitalMenu

DOMAIN = 'https://limit-connect.com'
OUTPUT_DIR = '/var/www/fina-connect/media/gastro/table_qr'
os.makedirs(OUTPUT_DIR, exist_ok=True)

menu = DigitalMenu.objects.get(slug='korpas-doo-siroki-sor')
tables = TableQR.objects.filter(menu=menu).order_by('table_number')

for tqr in tables:
    url = f'{DOMAIN}/gastro-menu/menu/{menu.slug}/?table={tqr.table_number}'
    
    # Generate QR
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#1a0a06', back_color='white')
    
    # Add label below QR
    # (Pillow: create larger canvas, paste QR, add text)
    qr_w, qr_h = img.size
    canvas = Image.new('RGB', (qr_w, qr_h + 60), 'white')
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    
    label = tqr.table_number
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 28)
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(((qr_w - text_w) / 2, qr_h + 10), label, fill='#1a0a06', font=font)
    
    # Save
    filename = f'qr_{tqr.table_number.replace(" ", "_").lower()}.png'
    filepath = os.path.join(OUTPUT_DIR, filename)
    canvas.save(filepath)
    
    # Update model
    tqr.qr_image = f'gastro/table_qr/{filename}'
    tqr.save(update_fields=['qr_image'])
    
    print(f'  ✓ {tqr.table_number} → {filename}')

print(f'\nGenerirano {tables.count()} QR kodova u {OUTPUT_DIR}')
```

### Preduvjet:
```bash
pip install qrcode[pil]
```

### Provjera:
```bash
ls -la media/gastro/table_qr/*.png | wc -l  # treba biti 20
# Otvori jedan PNG i skeniraj mobitelom — treba otvoriti menu
```

---

## A2 — Public narudžba flow (gost → kuhinja)

### Što treba:
Gost skenira QR → vidi menu → odabere stavke → pošalje narudžbu → kuhar vidi na displayu.

### View: `gastro_menu/views.py` — dodati:

```python
@require_POST
def public_order(request, slug):
    """Gost šalje narudžbu s public menija (bez logina)."""
    menu = get_object_or_404(DigitalMenu, slug=slug, is_active=True)
    
    data = json.loads(request.body)
    table_number = data.get('table', '')
    items = data.get('items', [])  # [{id: menuitem_id, qty: 1, notes: ''}]
    guest_name = data.get('name', '')
    
    if not items:
        return JsonResponse({'ok': False, 'error': 'Nema stavki'}, status=400)
    
    # Find or create TableQR
    table_qr = TableQR.objects.filter(
        company=menu.company, table_number=table_number
    ).first()
    
    # Create TableOrder
    from .models import TableOrder
    order_items = []
    total = Decimal('0')
    for item_data in items:
        mi = MenuItem.objects.filter(pk=item_data['id'], is_available=True).first()
        if mi:
            qty = int(item_data.get('qty', 1))
            order_items.append({
                'menu_item_id': mi.pk,
                'name': mi.name,
                'price': str(mi.price),
                'qty': qty,
                'notes': item_data.get('notes', ''),
            })
            total += mi.price * qty
    
    order = TableOrder.objects.create(
        table_qr=table_qr,
        company=menu.company,
        status='new',
        items=order_items,
        total=total,
    )
    
    # WhatsApp notifikacija kuharu
    try:
        from core.whatsapp import send_text
        items_text = '\n'.join(f"  {i['qty']}x {i['name']}" + (f" ({i['notes']})" if i['notes'] else '') for i in order_items)
        send_text(
            phone='385913912621',  # Kruljac
            message=f'🍽️ NOVA NARUDŽBA #{order.pk}\n'
                    f'Stol: {table_number}\n'
                    f'{items_text}\n'
                    f'Ukupno: {total} EUR',
            company_id=str(menu.company.pk),
        )
    except Exception:
        pass
    
    return JsonResponse({
        'ok': True,
        'order_id': order.pk,
        'total': str(total),
        'message': f'Narudžba #{order.pk} primljena! Stol: {table_number}',
    })
```

### URL:
```python
path('menu/<slug:slug>/order/', views.public_order, name='public_order'),
```

### Frontend (dodati u public_menu.html):
- Košarica (JavaScript, local state)
- "+" gumb kraj svake stavke
- Floating košarica button s brojem stavki
- Modal za potvrdu (ime, stol automatski iz URL ?table=)
- POST na `/gastro-menu/menu/{slug}/order/`
- Success screen s brojem narudžbe

### Template: `templates/gastro_menu/public_menu.html` — dodati JS:

```javascript
// Košarica state
let cart = [];

function addToCart(itemId, name, price) {
    const existing = cart.find(i => i.id === itemId);
    if (existing) existing.qty++;
    else cart.push({id: itemId, name, price: parseFloat(price), qty: 1, notes: ''});
    updateCartUI();
}

function updateCartUI() {
    const count = cart.reduce((s, i) => s + i.qty, 0);
    const total = cart.reduce((s, i) => s + i.price * i.qty, 0);
    document.getElementById('cart-count').textContent = count;
    document.getElementById('cart-total').textContent = total.toFixed(2);
    document.getElementById('cart-btn').style.display = count > 0 ? 'flex' : 'none';
}

async function submitOrder() {
    const table = new URLSearchParams(window.location.search).get('table') || '';
    const name = document.getElementById('guest-name').value || '';
    const resp = await fetch(window.location.pathname + 'order/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({table, name, items: cart})
    });
    const data = await resp.json();
    if (data.ok) {
        cart = [];
        updateCartUI();
        // Show success
        document.getElementById('order-success').style.display = 'block';
        document.getElementById('order-msg').textContent = data.message;
    }
}
```

### Kuhinjski display:
Kreirati `gastro_menu/views.py` → `kitchen_display(request)`:
- Login required (samo osoblje)
- Real-time: HTMX poll svakih 10s ili WebSocket
- Prikazuje: nove narudžbe, stol, stavke, status
- Gumb "Gotovo" → status='ready'

### URL:
```python
path('kitchen/', views.kitchen_display, name='kitchen'),
```

---

## GIT:
```bash
git add scripts/generate_table_qr.py \
        gastro_menu/views.py \
        gastro_menu/urls.py \
        templates/gastro_menu/public_menu.html \
        templates/gastro_menu/kitchen_display.html \
        media/gastro/table_qr/
git commit -m "feat: Široki Šor QR kodovi + narudžba flow + kuhinjski display"
```

---

## PROVJERA:
1. `ls media/gastro/table_qr/*.png | wc -l` → 20
2. Skeniraj QR s mobitelom → otvara se menu
3. Dodaj stavke u košaricu → pošalji narudžbu
4. WhatsApp stigne Kruljcu
5. `/gastro-menu/kitchen/` prikazuje novu narudžbu
6. Klik "Gotovo" → status=ready
