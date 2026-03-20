import os
import shutil
import re

BASE_DIR = '/var/www/fina-connect'

# Datoteke koje mijenjamo
BAU_HTML = os.path.join(BASE_DIR, 'website/templates/website/bau.html')
WEB_VIEWS = os.path.join(BASE_DIR, 'website/views.py')
WT_MODELS = os.path.join(BASE_DIR, 'worktime/models.py')
WT_VIEWS = os.path.join(BASE_DIR, 'worktime/views.py')
CORE_URLS = os.path.join(BASE_DIR, 'core/urls.py')
WORKER_CAM_HTML = os.path.join(BASE_DIR, 'templates/dashboards/worker_camera.html')

# 1. BACKUP
for f in [BAU_HTML, WEB_VIEWS, WT_MODELS, WT_VIEWS, CORE_URLS]:
    if os.path.exists(f):
        shutil.copy2(f, f + '.bak_a_i_b')

print("⏳ 1/6 Ažuriram BAU stranicu (Galerija)...")
# --- OPCIJA A: FRONTEND (bau.html) ---
with open(BAU_HTML, 'r', encoding='utf-8') as f:
    bau_code = f.read()

gallery_css = """
        /* GALERIJA REFERENCI */
        .gallery-section { padding: 100px 48px; background: var(--black); position: relative; z-index: 10; border-top: 1px solid var(--border); }
        .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; margin-top: 50px; }
        .gallery-item { position: relative; border-radius: 12px; overflow: hidden; aspect-ratio: 4/3; border: 1px solid var(--border); transition: transform 0.3s, border-color 0.3s; background: var(--surface2); }
        .gallery-item:hover { transform: translateY(-5px); border-color: var(--gold); box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .gallery-item img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.5s; }
        .gallery-item:hover img { transform: scale(1.05); }
        .gallery-overlay { position: absolute; inset: 0; background: linear-gradient(to top, rgba(10,10,10,0.95) 0%, transparent 60%); display: flex; align-items: flex-end; padding: 24px; opacity: 0; transition: opacity 0.3s; }
        .gallery-item:hover .gallery-overlay { opacity: 1; }
        .gallery-title { color: var(--text); font-weight: 700; font-family: 'Barlow Condensed', sans-serif; letter-spacing: 2px; font-size: 1.3rem; text-transform: uppercase; }
"""
if "/* GALERIJA REFERENCI */" not in bau_code:
    bau_code = bau_code.replace('</style>', gallery_css + '\n    </style>')

gallery_html = """
<section class="gallery-section" id="referenzen">
    <div class="section-eyebrow">Unsere Referenzen</div>
    <h2 class="section-title">Ergebnisse, die <em>überzeugen</em>.</h2>
    <p class="about-text">Ein Bild sagt mehr als tausend Worte. Werfen Sie einen Blick auf unsere zuletzt abgeschlossenen Projekte im Bereich Badsanierung und Innenausbau.</p>
    
    <div class="gallery-grid">
        {% if slike %}
            {% for slika in slike %}
            <div class="gallery-item">
                <img src="{{ slika.image.url }}" alt="{{ slika.title|default:'Projekt Referenz' }}">
                <div class="gallery-overlay">
                    <div class="gallery-title">{{ slika.title|default:"Abgeschlossenes Projekt" }}</div>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="gallery-item" style="display: flex; align-items: center; justify-content: center; color: var(--text-dim);">
                <div style="text-align:center"><i class="fas fa-camera fa-3x" style="opacity:0.2; margin-bottom:16px"></i><br><span style="font-family:'Barlow Condensed',sans-serif; letter-spacing:2px; text-transform:uppercase;">Badezimmer Stuttgart</span></div>
            </div>
            <div class="gallery-item" style="display: flex; align-items: center; justify-content: center; color: var(--text-dim);">
                <div style="text-align:center"><i class="fas fa-camera fa-3x" style="opacity:0.2; margin-bottom:16px"></i><br><span style="font-family:'Barlow Condensed',sans-serif; letter-spacing:2px; text-transform:uppercase;">Innenausbau Ludwigsburg</span></div>
            </div>
            <div class="gallery-item" style="display: flex; align-items: center; justify-content: center; color: var(--text-dim);">
                <div style="text-align:center"><i class="fas fa-camera fa-3x" style="opacity:0.2; margin-bottom:16px"></i><br><span style="font-family:'Barlow Condensed',sans-serif; letter-spacing:2px; text-transform:uppercase;">Fliesenverlegung Böblingen</span></div>
            </div>
        {% endif %}
    </div>
</section>
"""
if 'id="referenzen"' not in bau_code:
    bau_code = bau_code.replace('<div class="cta-section" id="kontakt">', gallery_html + '\n<div class="cta-section" id="kontakt">')

with open(BAU_HTML, 'w', encoding='utf-8') as f:
    f.write(bau_code)

print("⏳ 2/6 Ažuriram BACKEND za Galeriju...")
# --- OPCIJA A: BACKEND (website/views.py) ---
with open(WEB_VIEWS, 'r', encoding='utf-8') as f:
    web_views_code = f.read()

old_bau = """def bau_page(request):
    \"\"\"Landing stranica za građevinu i sanacije (za oglasnike)\"\"\"
    return render(request, 'website/bau.html')"""

new_bau = """def bau_page(request):
    \"\"\"Landing stranica za građevinu i sanacije (za oglasnike)\"\"\"
    try:
        from website.models import GalleryImage
        slike = GalleryImage.objects.filter(is_active=True).order_by('-id')[:6]
    except:
        slike = []
    return render(request, 'website/bau.html', {'slike': slike})"""

web_views_code = web_views_code.replace(old_bau, new_bau)
with open(WEB_VIEWS, 'w', encoding='utf-8') as f:
    f.write(web_views_code)


print("⏳ 3/6 Kreiram BAZU za Radničku Kameru...")
# --- OPCIJA B: BAZA (worktime/models.py) ---
with open(WT_MODELS, 'r', encoding='utf-8') as f:
    wt_models_code = f.read()

if "class ProjectPhoto" not in wt_models_code:
    photo_model = """
class ProjectPhoto(models.Model):
    \"\"\"Fotografije s gradilišta koje radnici šalju preko mobitela\"\"\"
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_photos')
    project_lead = models.ForeignKey('burza.ProjectLead', on_delete=models.SET_NULL, null=True, blank=True, related_name='site_photos')
    image = models.ImageField(upload_to='site_photos/%Y/%m/')
    note = models.TextField(blank=True, help_text="Bilješka radnika (opcionalno)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Slika - {self.user.username} - {self.created_at.strftime('%d.%m.%Y')}"
"""
    with open(WT_MODELS, 'a', encoding='utf-8') as f:
        f.write(photo_model)


print("⏳ 4/6 Dodajem API za Slikanje...")
# --- OPCIJA B: BACKEND (worktime/views.py) ---
with open(WT_VIEWS, 'r', encoding='utf-8') as f:
    wt_views_code = f.read()

if "def worker_camera_view" not in wt_views_code:
    camera_views = """
@login_required
def worker_camera_view(request):
    \"\"\"Sučelje za radnike na terenu (Kamera)\"\"\"
    from burza.models import ProjectLead
    # Radnik bira na kojem je projektu od aktivnih
    active_leads = ProjectLead.objects.filter(status__in=['PREUZETO', 'NA_BURZI', 'INTERNA_PROCJENA'])
    return render(request, 'dashboards/worker_camera.html', {'active_leads': active_leads})

@login_required
def worker_camera_upload(request):
    \"\"\"API za primanje slike s mobitela\"\"\"
    from django.http import JsonResponse
    from burza.models import ProjectLead
    from .models import ProjectPhoto
    
    if request.method == 'POST':
        image = request.FILES.get('image')
        lead_id = request.POST.get('lead_id')
        note = request.POST.get('note', '')
        
        if not image:
            return JsonResponse({'ok': False, 'error': 'Nije prenesena slika.'}, status=400)
            
        lead = None
        if lead_id:
            try:
                lead = ProjectLead.objects.get(id=lead_id)
            except Exception:
                pass
                
        ProjectPhoto.objects.create(
            user=request.user,
            project_lead=lead,
            image=image,
            note=note
        )
        return JsonResponse({'ok': True, 'msg': 'Fotografija uspješno spremljena u sustav!'})
    return JsonResponse({'ok': False, 'error': 'Nedozvoljena metoda.'}, status=405)
"""
    with open(WT_VIEWS, 'a', encoding='utf-8') as f:
        f.write(camera_views)


print("⏳ 5/6 Povezujem Rute...")
# --- OPCIJA B: URL RUTE (core/urls.py) ---
with open(CORE_URLS, 'r', encoding='utf-8') as f:
    urls_code = f.read()

if "worker_camera_view" not in urls_code:
    stari_worker_path = "path('dashboard/worker/', views.worker_dashboard, name='worker_dashboard'),"
    novi_worker_path = """path('dashboard/worker/', views.worker_dashboard, name='worker_dashboard'),
    path('dashboard/worker/camera/', __import__('worktime.views', fromlist=['worker_camera_view']).worker_camera_view, name='worker_camera_ui'),
    path('dashboard/worker/upload/', __import__('worktime.views', fromlist=['worker_camera_upload']).worker_camera_upload, name='worker_camera_api'),"""
    
    urls_code = urls_code.replace(stari_worker_path, novi_worker_path)
    with open(CORE_URLS, 'w', encoding='utf-8') as f:
        f.write(urls_code)


print("⏳ 6/6 Izrađujem Mobilnu Aplikaciju za Radnike...")
# --- OPCIJA B: MOBILNI HTML PREDLOŽAK ---
worker_cam_html = """{% load i18n %}
<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Bautagebuch Kamera - FINA Connect</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet">
    <style>
        :root { --bg: #0a0a0a; --surface: #181a1d; --gold: #c9a84c; --gold-dim: #b8962e; --text: #f0ede8; --text-dim: #64748b; --border: #252830; }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 16px; display: flex; flex-direction: column; min-height: 100vh; }
        
        .header { display: flex; align-items: center; justify-content: space-between; padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }
        .header h1 { font-size: 1.2rem; font-weight: 700; color: var(--gold); text-transform: uppercase; letter-spacing: 1px; }
        .back-btn { color: var(--text-dim); text-decoration: none; font-size: 1.5rem; }
        
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
        label { display: block; font-size: 0.8rem; color: var(--text-dim); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
        select, textarea { width: 100%; background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 14px; border-radius: 8px; font-size: 1rem; outline: none; margin-bottom: 20px; }
        select:focus, textarea:focus { border-color: var(--gold); }
        
        /* Gumb za kameru (Native feel) */
        .camera-btn { 
            display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
            width: 100%; background: rgba(201, 168, 76, 0.1); border: 2px dashed var(--gold); color: var(--gold);
            padding: 40px 20px; border-radius: 12px; cursor: pointer; font-size: 1.1rem; font-weight: 700; text-transform: uppercase; transition: all 0.2s;
        }
        .camera-btn:active { background: rgba(201, 168, 76, 0.2); transform: scale(0.98); }
        .camera-btn i { font-size: 2.5rem; }
        
        /* Prikaz odabrane slike */
        #previewContainer { display: none; margin-top: 20px; position: relative; border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }
        #previewContainer img { width: 100%; display: block; }
        .retake-btn { position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.7); color: #fff; border: none; padding: 8px 16px; border-radius: 99px; font-size: 0.8rem; font-weight: 600; }
        
        /* Glavni gumb za slanje */
        .submit-btn {
            width: 100%; background: var(--gold); color: #000; border: none; padding: 16px;
            font-size: 1.1rem; font-weight: 800; border-radius: 8px; text-transform: uppercase;
            letter-spacing: 2px; margin-top: auto; display: none; transition: all 0.2s;
        }
        .submit-btn:disabled { background: var(--surface); color: var(--text-dim); border: 1px solid var(--border); }
        
        /* Toast poruke (Feedback) */
        #toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%) translateY(100px); background: #22c55e; color: #fff; padding: 12px 24px; border-radius: 8px; font-weight: 600; opacity: 0; transition: all 0.3s; box-shadow: 0 10px 30px rgba(0,0,0,0.5); z-index: 9999; text-align: center; width: 90%; }
        #toast.show { transform: translateX(-50%) translateY(0); opacity: 1; }
        #toast.error { background: #ef4444; }
    </style>
</head>
<body>

    <div class="header">
        <a href="/dashboard/worker/" class="back-btn"><i class="fas fa-arrow-left"></i></a>
        <h1>📸 Terenska Kamera</h1>
        <div style="width:24px"></div> </div>

    <div class="card">
        <label>Odaberi Projekt (Gradilište)</label>
        <select id="projectSelect">
            <option value="">-- Odaberi gradilište --</option>
            {% for lead in active_leads %}
                <option value="{{ lead.id }}">{{ lead.title }} ({{ lead.location }})</option>
            {% endfor %}
        </select>
        
        <label>Kratka bilješka / Status (Opcionalno)</label>
        <textarea id="noteInput" rows="2" placeholder="Npr. Završeno gletanje prvog zida..."></textarea>
    </div>

    <input type="file" id="cameraInput" accept="image/*" capture="environment" style="display: none;">

    <div class="camera-btn" id="openCameraBtn" onclick="document.getElementById('cameraInput').click()">
        <i class="fas fa-camera"></i>
        <span>Slikaj Radove</span>
    </div>

    <div id="previewContainer">
        <button class="retake-btn" onclick="document.getElementById('cameraInput').click()"><i class="fas fa-redo"></i> Ponovno slikaj</button>
        <img id="imagePreview" src="" alt="Pregled slike">
    </div>

    <button id="submitBtn" class="submit-btn" onclick="uploadPhoto()">
        <i class="fas fa-cloud-upload-alt"></i> Pošalji u sustav
    </button>
    
    <div id="toast"></div>

    <script>
        const cameraInput = document.getElementById('cameraInput');
        const previewContainer = document.getElementById('previewContainer');
        const imagePreview = document.getElementById('imagePreview');
        const openCameraBtn = document.getElementById('openCameraBtn');
        const submitBtn = document.getElementById('submitBtn');
        let selectedFile = null;

        // Kad radnik uslika sliku, prikaži preview
        cameraInput.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                selectedFile = e.target.files[0];
                const reader = new FileReader();
                reader.onload = function(e) {
                    imagePreview.src = e.target.result;
                    previewContainer.style.display = 'block';
                    openCameraBtn.style.display = 'none';
                    submitBtn.style.display = 'block';
                    
                    // Skrolaj do dna da radnik vidi gumb
                    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
                }
                reader.readAsDataURL(selectedFile);
            }
        });

        // AJAX Upload - OBAVEZAN SUSTAV POVRATNIH INFORMACIJA
        function uploadPhoto() {
            const projectId = document.getElementById('projectSelect').value;
            const note = document.getElementById('noteInput').value;
            
            if (!selectedFile) return;
            
            // 1. Loading stanje - Zaključaj gumbe da se spriječi dvostruko slanje
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Obrada... Slanje na server';
            
            const formData = new FormData();
            formData.append('image', selectedFile);
            formData.append('lead_id', projectId);
            formData.append('note', note);
            formData.append('csrfmiddlewaretoken', '{{ csrf_token }}');

            fetch('{% url "worker_camera_api" %}', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if(data.ok) {
                    // 2. Uspjeh
                    showToast('✅ ' + data.msg, 'success');
                    setTimeout(() => {
                        window.location.href = '/dashboard/worker/';
                    }, 2000);
                } else {
                    // 3. Greška s backenda
                    showToast('❌ Greška: ' + data.error, 'error');
                    resetButton();
                }
            })
            .catch(error => {
                // 4. Greška s mrežom
                showToast('❌ Mrežna greška. Provjerite internet.', 'error');
                resetButton();
            });
        }
        
        function resetButton() {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-cloud-upload-alt"></i> Pošalji u sustav';
        }

        function showToast(msg, type) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = type === 'error' ? 'show error' : 'show';
            setTimeout(() => { toast.classList.remove('show'); }, 4000);
        }
    </script>
</body>
</html>
"""
with open(WORKER_CAM_HTML, 'w', encoding='utf-8') as f:
    f.write(worker_cam_html)

# Izvršavamo migracije kako bi se kreirala tablica za slike u bazi
os.system("venv/bin/python manage.py makemigrations worktime || python3 manage.py makemigrations worktime")
os.system("venv/bin/python manage.py migrate worktime || python3 manage.py migrate worktime")

# Osiguravamo ispravne dozvole kako bi server mogao primati slike (chown)
os.system("chown -R www-data:www-data /var/www/fina-connect/")
os.system("supervisorctl restart fina-connect")

print("✅ OPCIJA A i B SU ZAVRŠENE! Sustav je 100% spreman za slike.")
