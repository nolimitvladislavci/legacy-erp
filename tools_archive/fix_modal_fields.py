import re
import os

print("🚀 Dodajem nedostajuća polja (Status, Cjelodnevni) u formu...")

template_path = '/var/www/fina-connect/appointments/templates/appointments/calendar.html'

if os.path.exists(template_path):
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_modal_body = """<div class="modal-body">
                    <div id="formErrors" class="alert alert-danger d-none"></div>
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Naslov</label>
                            <input type="text" class="form-control" name="title" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Klijent</label>
                            <select class="form-select" name="client">
                                <option value="">--- Interni ---</option>
                                {% for client in clients %}
                                <option value="{{ client.id }}">{{ client.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Početak</label>
                            <input type="datetime-local" class="form-control" id="id_start_time" name="start_time" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Kraj (Opcionalno)</label>
                            <input type="datetime-local" class="form-control" id="id_end_time" name="end_time">
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Tip termina</label>
                            <select class="form-select" name="appointment_type">
                                <option value="service">Kratka usluga</option>
                                <option value="rental">Dugoročni najam</option>
                                <option value="event">Događaj</option>
                                <option value="meeting" selected>Sastanak</option>
                            </select>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Resurs</label>
                            <select class="form-select" name="resource">
                                <option value="">--- Bez resursa ---</option>
                                {% for res in resources %}
                                <option value="{{ res.id }}">{{ res.name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-md-4 mb-3">
                            <label class="form-label">Status</label>
                            <select class="form-select" name="status">
                                <option value="scheduled">Planirano</option>
                                <option value="confirmed">Potvrđeno</option>
                                <option value="completed">Završeno</option>
                                <option value="cancelled">Otkazano</option>
                            </select>
                        </div>
                        <div class="col-md-4 mb-3 d-flex align-items-center mt-3">
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" id="id_is_all_day" name="is_all_day">
                                <label class="form-check-label ms-2" for="id_is_all_day">Cjelodnevni najam</label>
                            </div>
                        </div>
                        <div class="col-md-4 mb-3">
                            <label class="form-label">Boja u kalendaru</label>
                            <input type="color" class="form-control form-control-color w-100" name="color" value="#3b82f6">
                        </div>
                    </div>
                </div>"""

    # Zamjenjujemo staro tijelo forme novim, potpunim
    updated_content = re.sub(r'<div class="modal-body">.*?</div>\s*<div class="modal-footer">', new_modal_body + '\n                <div class="modal-footer">', content, flags=re.DOTALL)
    
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    print("✅ Forma uspješno popravljena!")
else:
    print("❌ Ne mogu pronaći calendar.html")

os.system("supervisorctl restart fina-connect")
print("✨ Sustav osvježen.")
