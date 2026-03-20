#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path

TARGET_FILE = Path('/var/www/fina-connect/appointments/templates/appointments/public/calendar.html')

print("🚀 POKRETANJE: Isporuka luksuznog interaktivnog kalendara...")

html_content = """{% load i18n %}
<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rezervacija | {{ service.name }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; }
        :root { --black: #0a0a0a; --dark: #111214; --surface: #181a1d; --border: #252830; --gold: #c9a84c; --white: #f0ede8; --muted: #4a5060; }
        body { background: var(--black); color: var(--white); font-family: 'Barlow', sans-serif; margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        
        .booking-container { background: var(--surface); border: 1px solid var(--border); width: 100%; max-width: 900px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 40px 80px rgba(0,0,0,0.5); }
        .header { background: var(--dark); padding: 40px; text-align: center; border-bottom: 1px solid var(--border); }
        .header h1 { font-family: 'Cormorant Garamond', serif; font-size: 2.5rem; font-weight: 300; margin: 0; color: var(--gold); }
        .header p { color: var(--muted); font-size: 0.9rem; letter-spacing: 2px; text-transform: uppercase; margin-top: 10px; }
        
        .body-content { display: grid; grid-template-columns: 1fr 1fr; }
        @media (max-width: 768px) { .body-content { grid-template-columns: 1fr; } }
        
        /* KALENDAR DIZAJN */
        .calendar-section { padding: 40px; border-right: 1px solid var(--border); }
        .month-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .month-nav button { background: none; border: 1px solid var(--border); color: var(--gold); padding: 5px 15px; cursor: pointer; transition: 0.3s; }
        .month-nav button:hover { background: var(--gold); color: var(--black); }
        .month-nav span { font-family: 'Barlow', sans-serif; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 2px; }
        
        .weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; font-size: 0.75rem; color: var(--muted); margin-bottom: 10px; }
        .days-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 5px; }
        .day { aspect-ratio: 1; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; cursor: pointer; border: 1px solid transparent; transition: 0.2s; }
        .day:hover:not(.disabled) { border-color: var(--gold); color: var(--gold); }
        .day.selected { background: var(--gold); color: var(--black); font-weight: bold; }
        .day.disabled { color: var(--border); cursor: not-allowed; text-decoration: line-through; }
        .day.empty { cursor: default; }

        /* VREMENA (SLOTS) DIZAJN */
        .slots-section { padding: 40px; background: var(--dark); display: flex; flex-direction: column; }
        .slots-title { font-size: 0.8rem; letter-spacing: 2px; text-transform: uppercase; color: var(--muted); margin-bottom: 20px; text-align: center; }
        .slots-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 10px; }
        .slot-btn { background: var(--surface); border: 1px solid var(--border); color: var(--white); padding: 12px 0; font-family: 'Barlow', sans-serif; cursor: pointer; transition: 0.3s; text-align: center; }
        .slot-btn:hover { border-color: var(--gold); color: var(--gold); }
        .slot-btn.selected { background: var(--gold); color: var(--black); border-color: var(--gold); font-weight: bold; }
        .no-slots { text-align: center; color: var(--muted); font-style: italic; font-size: 0.9rem; padding: 20px 0; }
        
        /* FORMA DIZAJN (Korak 3) */
        .form-section { padding: 40px; display: none; grid-column: 1 / -1; background: var(--surface); border-top: 1px solid var(--border); }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; font-size: 0.75rem; letter-spacing: 1px; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
        .form-group input { width: 100%; background: var(--dark); border: 1px solid var(--border); color: var(--white); padding: 15px; font-family: 'Barlow', sans-serif; font-size: 1rem; }
        .form-group input:focus { outline: none; border-color: var(--gold); }
        
        .btn-submit { display: block; width: 100%; background: var(--gold); color: var(--black); padding: 18px; border: none; font-family: 'Barlow', sans-serif; font-weight: 700; font-size: 1rem; letter-spacing: 3px; text-transform: uppercase; cursor: pointer; transition: 0.3s; margin-top: 30px; }
        .btn-submit:hover { background: #e8c96a; }
        .btn-back { display: block; text-align: center; margin-top: 15px; color: var(--muted); cursor: pointer; font-size: 0.8rem; text-decoration: underline; }

        /* LOADER */
        .loader { display: none; text-align: center; color: var(--gold); font-size: 0.8rem; letter-spacing: 2px; text-transform: uppercase; margin-top: 20px; }
    </style>
</head>
<body>

<div class="booking-container">
    <div class="header">
        <h1>{{ service.name }}</h1>
        <p>Trajanje: {{ service.duration|time:"H:i" }} | Cijena: {{ service.price }} €</p>
    </div>

    <div class="body-content" id="step1">
        <div class="calendar-section">
            <div class="month-nav">
                <button onclick="changeMonth(-1)">&#8592;</button>
                <span id="monthDisplay">Srpanj 2024</span>
                <button onclick="changeMonth(1)">&#8594;</button>
            </div>
            <div class="weekdays">
                <div>Pon</div><div>Uto</div><div>Sri</div><div>Čet</div><div>Pet</div><div>Sub</div><div>Ned</div>
            </div>
            <div class="days-grid" id="daysGrid">
                </div>
        </div>
        
        <div class="slots-section">
            <div class="slots-title" id="slotsTitle">Odaberite datum</div>
            <div class="slots-grid" id="slotsGrid">
                <div class="no-slots">Kliknite na datum u kalendaru za prikaz slobodnih termina.</div>
            </div>
            <div class="loader" id="slotsLoader">Tražim slobodne termine...</div>
        </div>
    </div>

    <div class="form-section" id="step2">
        <h2 style="font-family:'Cormorant Garamond', serif; font-size:2rem; margin-top:0; color:var(--gold);">Vaši podaci</h2>
        <p style="color:var(--muted); margin-bottom:30px;">Termin: <strong id="summaryDate" style="color:var(--white);"></strong> u <strong id="summaryTime" style="color:var(--white);"></strong></p>
        
        <form id="bookingForm">
            <input type="hidden" id="serviceId" value="{{ service.id }}">
            <input type="hidden" id="selectedDate">
            <input type="hidden" id="selectedTime">
            
            <div class="form-group">
                <label>Ime i prezime</label>
                <input type="text" id="clientName" required>
            </div>
            <div class="form-group">
                <label>Email adresa</label>
                <input type="email" id="clientEmail" required>
            </div>
            <div class="form-group">
                <label>Telefon / WhatsApp</label>
                <input type="text" id="clientPhone" required>
            </div>
            
            <button type="submit" class="btn-submit" id="submitBtn">Potvrdi rezervaciju</button>
            <div class="btn-back" onclick="goBackToCalendar()">&#8592; Natrag na kalendar</div>
        </form>
    </div>
</div>

<script>
    const serviceId = document.getElementById('serviceId').value;
    let currentDate = new Date();
    let selectedDateStr = null;

    function renderCalendar() {
        const grid = document.getElementById('daysGrid');
        grid.innerHTML = '';
        
        const year = currentDate.getFullYear();
        const month = currentDate.getMonth();
        
        const monthsHR = ['Siječanj', 'Veljača', 'Ožujak', 'Travanj', 'Svibanj', 'Lipanj', 'Srpanj', 'Kolovoz', 'Rujan', 'Listopad', 'Studeni', 'Prosinac'];
        document.getElementById('monthDisplay').innerText = `${monthsHR[month]} ${year}`;
        
        const firstDayOfMonth = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        
        // Ponedjeljak je 1, Nedjelja je 0
        let startDay = firstDayOfMonth === 0 ? 6 : firstDayOfMonth - 1;
        
        const today = new Date();
        today.setHours(0,0,0,0);
        
        for (let i = 0; i < startDay; i++) {
            grid.innerHTML += `<div class="day empty"></div>`;
        }
        
        for (let day = 1; day <= daysInMonth; day++) {
            const dateObj = new Date(year, month, day);
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            
            let classNames = 'day';
            if (dateObj < today) classNames += ' disabled';
            if (dateStr === selectedDateStr) classNames += ' selected';
            
            if (dateObj < today) {
                grid.innerHTML += `<div class="${classNames}">${day}</div>`;
            } else {
                grid.innerHTML += `<div class="${classNames}" onclick="selectDate('${dateStr}')">${day}</div>`;
            }
        }
    }

    function changeMonth(offset) {
        currentDate.setMonth(currentDate.getMonth() + offset);
        renderCalendar();
    }

    function selectDate(dateStr) {
        selectedDateStr = dateStr;
        renderCalendar(); // Da posivi ostale i pozeleni odabrani
        
        // Formatiraj za prikaz HR
        const [y, m, d] = dateStr.split('-');
        document.getElementById('slotsTitle').innerText = `Slobodni termini: ${d}.${m}.${y}.`;
        
        fetchSlots(dateStr);
    }

    function fetchSlots(dateStr) {
        const grid = document.getElementById('slotsGrid');
        const loader = document.getElementById('slotsLoader');
        
        grid.innerHTML = '';
        loader.style.display = 'block';
        
        // Pozivamo tvoj već postojeći Django Backend
        fetch(`/appointments/api/booking/slots/?date=${dateStr}&service_id=${serviceId}`)
            .then(res => res.json())
            .then(data => {
                loader.style.display = 'none';
                if (data.slots && data.slots.length > 0) {
                    data.slots.forEach(time => {
                        grid.innerHTML += `<div class="slot-btn" onclick="selectTime('${time}')">${time}</div>`;
                    });
                } else {
                    grid.innerHTML = '<div class="no-slots">Nema slobodnih termina za ovaj dan.</div>';
                }
            })
            .catch(err => {
                loader.style.display = 'none';
                grid.innerHTML = '<div class="no-slots" style="color:var(--red);">Greška pri dohvatu termina.</div>';
            });
    }

    function selectTime(timeStr) {
        document.getElementById('selectedDate').value = selectedDateStr;
        document.getElementById('selectedTime').value = timeStr;
        
        const [y, m, d] = selectedDateStr.split('-');
        document.getElementById('summaryDate').innerText = `${d}.${m}.${y}.`;
        document.getElementById('summaryTime').innerText = timeStr;
        
        document.getElementById('step1').style.display = 'none';
        document.getElementById('step2').style.display = 'block';
    }

    function goBackToCalendar() {
        document.getElementById('step2').style.display = 'none';
        document.getElementById('step1').style.display = 'grid'; // ili flex, ovisi o mobitelu
    }

    // Slanje Forme na tvoj postojeći backend
    document.getElementById('bookingForm').addEventListener('submit', function(e) {
        e.preventDefault();
        
        const btn = document.getElementById('submitBtn');
        btn.innerText = 'OBRADA...';
        btn.disabled = true;
        
        const payload = {
            service_id: serviceId,
            date: document.getElementById('selectedDate').value,
            time: document.getElementById('selectedTime').value,
            name: document.getElementById('clientName').value,
            email: document.getElementById('clientEmail').value,
            phone: document.getElementById('clientPhone').value,
            whatsapp: document.getElementById('clientPhone').value
        };
        
        fetch('/appointments/api/booking/submit/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById('step2').innerHTML = `
                    <div style="text-align:center; padding: 40px 0;">
                        <h2 style="font-family:'Cormorant Garamond', serif; color:var(--gold); font-size:3rem; margin-bottom:10px;">Hvala Vam.</h2>
                        <p style="color:var(--light);">Vaš termin je uspješno rezerviran.</p>
                        <a href="/" style="display:inline-block; margin-top:30px; color:var(--gold); border:1px solid var(--gold); padding:10px 20px; text-decoration:none; text-transform:uppercase; letter-spacing:2px; font-size:0.8rem;">Povratak na naslovnicu</a>
                    </div>
                `;
            } else {
                alert("Greška: " + (data.error || "Pokušajte ponovno."));
                btn.innerText = 'Potvrdi rezervaciju';
                btn.disabled = false;
            }
        });
    });

    // Helper za CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Inicijalizacija pri učitavanju
    renderCalendar();
</script>

</body>
</html>
"""

# Upisivanje u datoteku
os.makedirs(TARGET_FILE.parent, exist_ok=True)
TARGET_FILE.write_text(html_content, encoding='utf-8')
print(f"✅ Kalendar instaliran u: {TARGET_FILE.name}")

os.system("chown -R www-data:www-data /var/www/fina-connect")
os.system("supervisorctl restart fina-connect")

print("✨ ZAVRŠENO! Osvježi svoju javnu stranicu, klikni na Rezerviraj termin i isprobaj novi kalendar.")
