import os

print("🚀 MASTER RESET: Kreiranje čistog javnog Booking Frontenda...")

base_dir = '/var/www/fina-connect'
public_templates_dir = f'{base_dir}/appointments/templates/appointments/public'

# 1. Čišćenje starog nereda i osiguravanje strukture
os.makedirs(public_templates_dir, exist_ok=True)

# ==========================================
# 2. GENERIRANJE INDEX.HTML (Katalog usluga)
# ==========================================
index_html = """<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Online Rezervacije | LIMIT CONNECT</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: #f8fafc; font-family: 'Segoe UI', system-ui, sans-serif; }
        .hero { background: #0f172a; padding: 60px 0; text-align: center; color: white; border-bottom: 5px solid #c9a84c; }
        .hero h1 { font-weight: 700; letter-spacing: 1px; }
        .hero span { color: #c9a84c; }
        .service-card { background: white; border-radius: 16px; border: none; padding: 25px; transition: all 0.3s; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); text-align: center; cursor: pointer; text-decoration: none; color: inherit; display: block; height: 100%; }
        .service-card:hover { transform: translateY(-5px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); border-color: #3b82f6; }
        .service-icon { width: 60px; height: 60px; background: #eff6ff; color: #3b82f6; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; margin: 0 auto 15px; }
        .service-price { font-weight: 700; color: #10b981; font-size: 1.1rem; }
    </style>
</head>
<body>
    <div class="hero">
        <h1>VISKOVIC <span>GROUP</span></h1>
        <p class="lead mt-2 text-light opacity-75">Odaberite uslugu i rezervirajte svoj termin online.</p>
    </div>
    <div class="container mt-5 mb-5">
        <div class="row g-4 justify-content-center">
            {% for service in services %}
            <div class="col-md-4 col-sm-6">
                <a href="{% url 'public_booking_calendar' service.id %}" class="service-card">
                    <div class="service-icon"><i class="fas fa-calendar-check"></i></div>
                    <h4 class="mb-2" style="font-weight: 600; color: #0f172a;">{{ service.name }}</h4>
                    <p class="text-muted" style="font-size: 0.9rem;">{{ service.description|truncatechars:80 }}</p>
                    <div class="d-flex justify-content-between align-items-center mt-4 pt-3 border-top">
                        <span class="badge bg-light text-dark"><i class="far fa-clock me-1"></i> {{ service.duration }}</span>
                        {% if service.price %}<div class="service-price">{{ service.price }} €</div>{% endif %}
                    </div>
                </a>
            </div>
            {% empty %}
            <div class="col-12 text-center text-muted mt-5">
                <i class="fas fa-box-open fs-1 mb-3"></i>
                <h5>Trenutno nema aktivnih usluga za online rezervaciju.</h5>
                <p>Molimo prijavite se u sustav i kreirajte usluge u Django Adminu.</p>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>"""

with open(os.path.join(public_templates_dir, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(index_html)
print("✅ index.html (Javni katalog) savršeno generiran.")


# ==========================================
# 3. GENERIRANJE CALENDAR.HTML (Smart Forma)
# ==========================================
calendar_html = """<!DOCTYPE html>
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
        .top-nav span { color: #c9a84c; }
        .main-container { max-width: 900px; margin: 40px auto; background: white; border-radius: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); overflow: hidden; }
        .slot-btn { width: 100%; text-align: center; padding: 10px; border: 1px solid #10b981; color: #10b981; background: white; border-radius: 8px; font-weight: 600; transition: all 0.2s; margin-bottom: 10px; }
        .slot-btn:hover, .slot-btn.selected { background: #10b981; color: white; transform: translateY(-2px); }
        .info-panel { background: #f8fafc; padding: 30px; border-right: 1px solid #e2e8f0; height: 100%; }
        .date-picker { padding: 30px; }
        #slots-container { max-height: 400px; overflow-y: auto; padding-right: 10px; }
        #slots-container::-webkit-scrollbar { width: 6px; }
        #slots-container::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 10px; }
        .payment-option { border: 2px solid #e2e8f0; border-radius: 12px; padding: 15px; cursor: pointer; transition: all 0.2s; height: 100%; }
        .payment-option:hover { border-color: #cbd5e1; }
        .payment-option.selected { border-color: #3b82f6; background: #eff6ff; }
        .revolut-box { background: #f1f5f9; border-radius: 12px; padding: 20px; text-align: left; border-left: 5px solid #000; }
    </style>
</head>
<body>
    <div class="top-nav">
        <a href="{% url 'public_booking_index' %}" class="text-decoration-none text-muted"><i class="fas fa-arrow-left me-2"></i> Natrag</a>
        <h4>VISKOVIC <span>GROUP</span></h4>
    </div>

    <div class="main-container">
        <div class="row g-0">
            <div class="col-md-4 info-panel">
                <h3 style="font-weight: 700; color: #0f172a;">{{ service.name }}</h3>
                <p class="text-muted mt-2">{{ service.description }}</p>
                <div class="mt-4 pt-3 border-top">
                    <div class="d-flex align-items-center mb-3 text-muted"><i class="far fa-clock fs-5 me-3" style="color:#3b82f6;"></i> <span>{{ service.duration }}</span></div>
                    {% if service.price %}
                    <div class="d-flex align-items-center text-muted"><i class="fas fa-euro-sign fs-5 me-3" style="color:#10b981;"></i> <span>{{ service.price }} €</span></div>
                    {% endif %}
                </div>
            </div>
            
            <div class="col-md-8 date-picker">
                <h5 class="mb-4" style="font-weight: 600;">1. Odaberite datum</h5>
                <div class="row">
                    <div class="col-sm-6 mb-4">
                        <input type="date" id="dateSelect" class="form-control form-control-lg">
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
                            <input type="text" class="form-control" id="clientWhatsapp" placeholder="WhatsApp broj (Opcionalno)">
                        </div>

                        <h5 class="mb-3" style="font-weight: 600;">3. Način plaćanja</h5>
                        <div class="row mb-4 g-3">
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
                    <p class="text-muted mb-2">Molimo izvršite uplatu kako bi termin bio potvrđen.</p>
                    <hr>
                    <div class="row">
                        <div class="col-sm-6 mb-2"><strong>Iznos:</strong> <span class="fs-5" id="revAmount"></span> €</div>
                        <div class="col-sm-6 mb-2"><strong>IBAN:</strong> <br><span style="font-family:monospace; background:#e2e8f0; padding:2px 6px; border-radius:4px;">HR12 1234 5678 9012 3456 7</span></div>
                    </div>
                    <div class="mt-4">
                        <a href="#" id="waLink" target="_blank" class="btn btn-success w-100 py-2" style="font-weight:600; background:#25D366; border-color:#25D366;">
                            <i class="fab fa-whatsapp fs-5 me-2"></i> Javi nam se putem WhatsAppa
                        </a>
                    </div>
                </div>

                <div id="invoiceInfo" class="d-none mt-4">
                    <div class="alert alert-primary">
                        <i class="fas fa-envelope fs-4 mb-2"></i><br>Ponuda za plaćanje stiže na Vaš email.
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
                    container.innerHTML = '<div class="alert alert-light text-center">Nema slobodnih termina za ovaj datum.</div>';
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

with open(os.path.join(public_templates_dir, 'calendar.html'), 'w', encoding='utf-8') as f:
    f.write(calendar_html)
print("✅ calendar.html (Smart Forma) savršeno generiran.")

# 4. Dozvole
os.system(f"chown -R www-data:www-data {public_templates_dir}")
print("✨ Sve predloške smo postavili na pravo mjesto.")
