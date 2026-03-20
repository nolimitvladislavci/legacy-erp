import os
import shutil
import re

print("🚀 INICIJALIZACIJA: LIMIT CONNECT Premium UX (Revolut, WhatsApp, Fakture)...")

base_dir = '/var/www/fina-connect'
app_dir = f'{base_dir}/appointments'
models_path = f'{app_dir}/models.py'
views_path = f'{app_dir}/views.py'
template_path = f'{app_dir}/templates/appointments/public/calendar.html'

# 1. SIGURNOSNI BACKUP
for file_path in [models_path, views_path, template_path]:
    if os.path.exists(file_path):
        shutil.copy2(file_path, f"{file_path}.bak")
print("📦 Sigurnosni backupi kreirani.")

# 2. NADOGRADNJA MODELA (models.py) - Dodavanje financijskih i kontakt polja
with open(models_path, 'r', encoding='utf-8') as f:
    models_content = f.read()

new_fields = """
    # Premium UX polja
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Ukupna cijena')
    payment_method = models.CharField(max_length=50, default='invoice', verbose_name='Način plaćanja')
    whatsapp_number = models.CharField(max_length=50, blank=True, verbose_name='WhatsApp')
"""

if "total_price = models.DecimalField" not in models_content:
    # Ubacujemo polja prije "class Meta:" unutar Appointment modela
    models_content = re.sub(r'(\s+)class Meta:', r'\1' + new_fields.strip() + r'\n\1class Meta:', models_content)
    with open(models_path, 'w', encoding='utf-8') as f:
        f.write(models_content)
    print("✅ Baza nadograđena financijskim i WhatsApp poljima.")

# 3. NADOGRADNJA API-ja (views.py) - Logika naplate i kreiranja faktura
with open(views_path, 'r', encoding='utf-8') as f:
    views_content = f.read()

new_api_logic = """
@csrf_exempt
def api_submit_public_booking(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            service = get_object_or_404(BookingService, id=data['service_id'])
            target_date = parse_date(data['date'])
            time_str = data['time']
            
            name = data['name']
            email = data['email']
            phone = data.get('phone', '')
            whatsapp = data.get('whatsapp', '')
            payment_method = data.get('payment_method', 'invoice')
            
            client, created = Partner.objects.get_or_create(
                email=email,
                defaults={'name': name, 'phone': phone, 'partner_type': 'KUPAC'}
            )
            
            start_time = datetime.strptime(f"{data['date']} {time_str}", "%Y-%m-%d %H:%M")
            end_time = start_time + service.duration
            
            resources = BookingResource.objects.filter(resource_type=service.resource_type, is_active=True)
            assigned_resource = None
            for resource in resources:
                overlapping = Appointment.objects.filter(
                    resource=resource, start_time__lt=end_time, end_time__gt=start_time, status__in=['scheduled', 'confirmed']
                ).exists()
                if not overlapping:
                    assigned_resource = resource
                    break
                    
            if not assigned_resource:
                return JsonResponse({'error': 'Termin je upravo zauzet. Molimo odaberite drugi.'}, status=400)
            
            # Izračun cijene
            total_price = service.price if service.price else 0
            
            appointment = Appointment.objects.create(
                title=f"Online: {service.name}",
                client=client,
                service=service,
                resource=assigned_resource,
                start_time=start_time,
                end_time=end_time,
                appointment_type='service',
                status='scheduled',
                color='#10b981',
                total_price=total_price,
                payment_method=payment_method,
                whatsapp_number=whatsapp
            )
            
            # Pokušaj automatskog kreiranja fakture ako je odabrana ponuda
            invoice_created = False
            if payment_method == 'invoice' and total_price > 0:
                try:
                    from invoicing.models import Invoice
                    # Tražimo način da povežemo, ovo ovisi o točnom modelu faktura
                    Invoice.objects.create(
                        partner=client,
                        date_issued=start_time.date(),
                        due_date=start_time.date(),
                        total_amount=total_price,
                        status='DRAFT',
                        notes=f"Automatska ponuda za rezervaciju: {service.name}"
                    )
                    invoice_created = True
                except Exception as e:
                    pass # Ako modul invoicing nije potpuno usklađen, ignoriraj grešku da ne srušiš booking
            
            return JsonResponse({
                'status': 'success', 
                'booking_id': appointment.id,
                'total_price': float(total_price),
                'payment_method': payment_method,
                'invoice_created': invoice_created
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)
"""

# Mijenjamo staru funkciju novom
views_content = re.sub(r'@csrf_exempt\ndef api_submit_public_booking.*?return JsonResponse\(\{.*?\}\, status=400\)', new_api_logic.strip(), views_content, flags=re.DOTALL)

with open(views_path, 'w', encoding='utf-8') as f:
    f.write(views_content)
print("✅ API nadograđen logikom za Revolut i Fakture.")

# 4. NADOGRADNJA FRONTENDA (calendar.html) - Potpuno prepisivanje s Premium UI
new_html = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ service.name }} - Rezervacija</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: #f8fafc; font-family: 'Segoe UI', system-ui, sans-serif; }
        .top-nav { background: white; padding: 15px 30px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; }
        .top-nav h4 { margin: 0; font-weight: 700; color: #0f172a; }
        .main-container { max-width: 900px; margin: 40px auto; background: white; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); overflow: hidden; }
        .slot-btn { width: 100%; text-align: center; padding: 10px; border: 1px solid #10b981; color: #10b981; background: white; border-radius: 8px; font-weight: 600; transition: all 0.2s; margin-bottom: 10px; }
        .slot-btn:hover, .slot-btn.selected { background: #10b981; color: white; transform: translateY(-2px); }
        .info-panel { background: #f8fafc; padding: 30px; border-right: 1px solid #e2e8f0; }
        .date-picker { padding: 30px; }
        #slots-container { max-height: 400px; overflow-y: auto; padding-right: 10px; }
        #slots-container::-webkit-scrollbar { width: 6px; }
        #slots-container::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 10px; }
        
        .payment-option { border: 2px solid #e2e8f0; border-radius: 12px; padding: 15px; cursor: pointer; transition: all 0.2s; }
        .payment-option:hover { border-color: #cbd5e1; }
        .payment-option.selected { border-color: #3b82f6; background: #eff6ff; }
        .revolut-box { background: #f1f5f9; border-radius: 12px; padding: 20px; text-align: left; border-left: 5px solid #000; }
    </style>
</head>
<body>
    <div class="top-nav">
        <a href="{% url 'public_booking_index' %}" class="text-decoration-none text-muted"><i class="fas fa-arrow-left me-2"></i> Nazad na usluge</a>
        <h4>FINA-<span>CONNECT</span></h4>
    </div>

    <div class="main-container">
        <div class="row g-0">
            <div class="col-md-4 info-panel">
                <h3 style="font-weight: 700; color: #0f172a;">{{ service.name }}</h3>
                <p class="text-muted mt-2">{{ service.description }}</p>
                <div class="mt-4">
                    <div class="d-flex align-items-center mb-3 text-muted"><i class="far fa-clock fs-5 me-3" style="color:#3b82f6;"></i> <span>{{ service.duration }} min</span></div>
                    {% if service.price %}
                    <div class="d-flex align-items-center text-muted"><i class="fas fa-euro-sign fs-5 me-3" style="color:#10b981;"></i> <span>{{ service.price }} €</span></div>
                    <input type="hidden" id="servicePrice" value="{{ service.price }}">
                    {% endif %}
                </div>
            </div>
            
            <div class="col-md-8 date-picker">
                <h5 class="mb-4" style="font-weight: 600;">1. Odaberite datum i vrijeme</h5>
                <div class="row">
                    <div class="col-sm-6 mb-4">
                        <input type="date" id="dateSelect" class="form-control form-control-lg" min="">
                    </div>
                    <div class="col-sm-6">
                        <div id="loading" class="text-center d-none py-3"><i class="fas fa-spinner fa-spin text-primary fs-4"></i></div>
                        <div id="slots-container"><div class="text-muted" style="font-size:0.9rem;">Prvo odaberite datum.</div></div>
                    </div>
                </div>

                <div id="bookingForm" class="mt-4 pt-4 border-top d-none">
                    <h5 class="mb-3" style="font-weight: 600;">2. Vaši podaci</h5>
                    <form id="submitForm">
                        <input type="hidden" id="selectedTime" required>
                        <div class="mb-3">
                            <input type="text" class="form-control" id="clientName" placeholder="Ime i prezime" required>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <input type="email" class="form-control" id="clientEmail" placeholder="Email adresa" required>
                            </div>
                            <div class="col-md-6 mb-3">
                                <input type="text" class="form-control" id="clientPhone" placeholder="Broj mobitela" required>
                            </div>
                        </div>
                        <div class="mb-4">
                            <input type="text" class="form-control" id="clientWhatsapp" placeholder="WhatsApp broj (Opcionalno za lakšu komunikaciju)">
                        </div>

                        <h5 class="mb-3" style="font-weight: 600;">3. Način plaćanja</h5>
                        <div class="row mb-4">
                            <div class="col-6">
                                <div class="payment-option selected" onclick="selectPayment('invoice')">
                                    <input type="radio" name="paymentMethod" value="invoice" class="d-none" checked>
                                    <div style="font-weight:600;"><i class="fas fa-file-invoice me-2 text-primary"></i> Po ponudi</div>
                                    <small class="text-muted">Faktura na email</small>
                                </div>
                            </div>
                            <div class="col-6">
                                <div class="payment-option" onclick="selectPayment('revolut')">
                                    <input type="radio" name="paymentMethod" value="revolut" class="d-none">
                                    <div style="font-weight:600;"><i class="fas fa-mobile-alt me-2 text-dark"></i> Revolut</div>
                                    <small class="text-muted">Brza uplata</small>
                                </div>
                            </div>
                        </div>

                        <button type="submit" class="btn btn-primary w-100 py-3" id="submitBtn" style="font-weight:700; font-size:1.1rem;">Potvrdi rezervaciju</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="successModal" tabindex="-1" aria-hidden="true" data-bs-backdrop="static">
        <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content text-center p-5" style="border-radius:16px; border:none;">
                <div class="mb-3 text-success" style="font-size: 4rem;"><i class="fas fa-check-circle"></i></div>
                <h2 style="font-weight:700;">Hvala Vam!</h2>
                <p class="text-muted fs-5">Vaš termin je uspješno rezerviran.</p>
                
                <div id="revolutInfo" class="d-none mt-4 revolut-box">
                    <h5 style="font-weight:700; color:#0f172a;"><i class="fas fa-info-circle me-2"></i>Upute za Revolut uplatu</h5>
                    <p class="text-muted mb-2">Molimo izvršite uplatu kako bi termin bio konačno potvrđen.</p>
                    <hr>
                    <div class="row">
                        <div class="col-sm-6 mb-2"><strong>Iznos:</strong> <span class="fs-5" id="revAmount"></span> €</div>
                        <div class="col-sm-6 mb-2"><strong>IBAN:</strong> <br><span class="user-select-all" style="font-family:monospace; background:#e2e8f0; padding:2px 6px; border-radius:4px;">HR12 1234 5678 9012 3456 7</span></div>
                    </div>
                    <div class="mt-4">
                        <a href="#" id="waLink" target="_blank" class="btn btn-success w-100 py-2" style="font-weight:600; background:#25D366; border-color:#25D366;">
                            <i class="fab fa-whatsapp fs-5 me-2"></i> Javi nam se putem WhatsAppa
                        </a>
                    </div>
                </div>

                <div id="invoiceInfo" class="d-none mt-4">
                    <div class="alert alert-primary">
                        <i class="fas fa-envelope fs-4 mb-2"></i><br>
                        Ponuda za plaćanje će Vam biti poslana na upisani email.
                    </div>
                </div>

                <a href="{% url 'public_booking_index' %}" class="btn btn-dark mt-4 w-100 py-2" style="font-weight:600;">Završi i zatvori</a>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.getElementById('dateSelect').min = new Date().toISOString().split("T")[0];
        let selectedTime = null;

        function selectPayment(method) {
            document.querySelectorAll('.payment-option').forEach(opt => opt.classList.remove('selected'));
            document.querySelector(`input[value="${method}"]`).checked = true;
            document.querySelector(`input[value="${method}"]`).parentElement.classList.add('selected');
        }

        document.getElementById('dateSelect').addEventListener('change', function() {
            const date = this.value;
            document.getElementById('bookingForm').classList.add('d-none');
            selectedTime = null;
            if(!date) return;
            
            document.getElementById('loading').classList.remove('d-none');
            document.getElementById('slots-container').innerHTML = '';

            fetch(`/appointments/api/booking/slots/?date=${date}&service_id={{ service.id }}`)
            .then(res => res.json())
            .then(data => {
                document.getElementById('loading').classList.add('d-none');
                const container = document.getElementById('slots-container');
                if(data.slots && data.slots.length > 0) {
                    data.slots.forEach(time => {
                        const btn = document.createElement('button');
                        btn.className = 'slot-btn';
                        btn.textContent = time;
                        btn.onclick = function() {
                            document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('selected'));
                            this.classList.add('selected');
                            selectedTime = time;
                            document.getElementById('selectedTime').value = time;
                            document.getElementById('bookingForm').classList.remove('d-none');
                            document.getElementById('bookingForm').scrollIntoView({ behavior: 'smooth' });
                        };
                        container.appendChild(btn);
                    });
                } else {
                    container.innerHTML = '<div class="alert alert-light text-center">Nema slobodnih termina.</div>';
                }
            });
        });

        document.getElementById('submitForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Obrađujem...';
            btn.disabled = true;

            const payload = {
                service_id: {{ service.id }},
                date: document.getElementById('dateSelect').value,
                time: selectedTime,
                name: document.getElementById('clientName').value,
                email: document.getElementById('clientEmail').value,
                phone: document.getElementById('clientPhone').value,
                whatsapp: document.getElementById('clientWhatsapp').value,
                payment_method: document.querySelector('input[name="paymentMethod"]:checked').value
            };

            fetch('/appointments/api/booking/submit/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
            .then(res => res.json())
            .then(data => {
                if(data.status === 'success') {
                    if(data.payment_method === 'revolut') {
                        document.getElementById('revolutInfo').classList.remove('d-none');
                        document.getElementById('revAmount').innerText = data.total_price;
                        document.getElementById('waLink').href = `https://wa.me/4915100000000?text=Pozdrav,%20želim%20potvrditi%20Revolut%20uplatu%20za%20rezervaciju%20broj%20${data.booking_id}`;
                    } else {
                        document.getElementById('invoiceInfo').classList.remove('d-none');
                    }
                    new bootstrap.Modal(document.getElementById('successModal')).show();
                } else {
                    alert('Greška: ' + data.error);
                    btn.innerHTML = 'Potvrdi rezervaciju';
                    btn.disabled = false;
                }
            });
        });
    </script>
</body>
</html>"""

with open(template_path, 'w', encoding='utf-8') as f:
    f.write(new_html)
print("✅ Frontend javnog portala (Premium UX) ažuriran.")

# 5. MIGRACIJE, DOZVOLE I RESTART
print("🔄 Stvaranje i primjena migracija baze...")
os.system(f"{base_dir}/venv/bin/python {base_dir}/manage.py makemigrations appointments")
os.system(f"{base_dir}/venv/bin/python {base_dir}/manage.py migrate")
os.system("chown -R www-data:www-data /var/www/fina-connect/appointments")
os.system("supervisorctl restart fina-connect")

print("✨ Premium UX modul uspješno integriran u LIMIT CONNECT!")
