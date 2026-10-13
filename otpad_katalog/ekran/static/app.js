(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var GRESKA_MREZA = 'Nema veze s poslužiteljem. Provjeri mrežu i pokušaj ponovo.';
  var stanje = { dioId: null, prepoznatoBroj: '' };

  // ---------- pomoćne ----------
  function el(tag, atributi) {
    var n = document.createElement(tag);
    if (atributi) {
      Object.keys(atributi).forEach(function (k) {
        if (k === 'class') n.className = atributi[k];
        else n.setAttribute(k, atributi[k]);
      });
    }
    function dodaj(d) {
      if (d == null || d === false) return;
      if (Array.isArray(d)) { d.forEach(dodaj); return; }
      n.appendChild(typeof d === 'string' || typeof d === 'number' ? document.createTextNode(String(d)) : d);
    }
    for (var i = 2; i < arguments.length; i++) dodaj(arguments[i]);
    return n;
  }
  function isprazni(n) { while (n.firstChild) n.removeChild(n.firstChild); }

  function api(metoda, url, tijelo, zaglavlja) {
    var opcije = { method: metoda, headers: {} };
    if (typeof Blob !== 'undefined' && tijelo instanceof Blob) {      // slika: sirovi bajtovi
      opcije.headers['Content-Type'] = tijelo.type || 'application/octet-stream';
      opcije.headers['X-Requested-With'] = 'otpad';
      Object.keys(zaglavlja || {}).forEach(function (k) { opcije.headers[k] = zaglavlja[k]; });
      opcije.body = tijelo;
    } else if (tijelo) {
      opcije.headers['Content-Type'] = 'application/json';
      opcije.headers['X-Requested-With'] = 'otpad';
      opcije.body = JSON.stringify(tijelo);
    }
    return fetch(url, opcije).then(function (r) {
      return r.json().then(function (data) { return { ok: r.ok, status: r.status, data: data }; },
        function () {
          return { ok: false, status: r.status,
            data: { greska: 'Poslužitelj je vratio neočekivan odgovor (šifra ' + r.status + '). Pokušaj ponovo.' } };
        });
    }, function () {
      return { ok: false, status: 0, data: { greska: GRESKA_MREZA } };
    }).then(function (odg) {
      if (!odg.ok && !odg.data.greska) odg.data.greska = 'Greška ' + odg.status + '. Pokušaj ponovo.';
      return odg;
    });
  }

  function poruka(n, vrsta, tekst) {
    n.className = 'poruka' + (vrsta ? ' ' + vrsta : '');
    n.textContent = tekst || '';
    if (vrsta === 'greska') n.setAttribute('role', 'alert'); else n.removeAttribute('role');
  }

  // gumb onemogućen + tekst radnje dok traje zahtjev
  function zauzet(gumb, tekst, posao) {
    var staro = gumb.textContent;
    gumb.disabled = true; gumb.textContent = tekst;
    return Promise.resolve().then(posao).then(function (r) {
      gumb.disabled = false; gumb.textContent = staro; return r;
    }, function (e) {
      gumb.disabled = false; gumb.textContent = staro; throw e;
    });
  }

  function vozilo(v) {
    var ime = [v.marka, v.model, v.generacija].filter(Boolean).join(' ');
    var godine = v.od ? ' (' + v.od + '–' + (v.do ? v.do : 'danas') + ')' : '';
    return ime + godine;
  }
  function cijena(s) { return s == null ? '' : String(s).replace('.', ',') + ' €'; }

  // ---------- kartice ----------
  var TABOVI = ['trazi', 'novi', 'radu', 'stalaza', 'unos'];
  function tabPrebaci(ime) {
    TABOVI.forEach(function (t) {
      var aktivan = t === ime;
      $('tab-' + t).setAttribute('aria-selected', aktivan ? 'true' : 'false');
      $('tab-' + t).tabIndex = aktivan ? 0 : -1;
      $('panel-' + t).hidden = !aktivan;
    });
    if (ime === 'unos') osvjeziUnos();
    else if (ime === 'trazi') $('q').focus();
    document.dispatchEvent(new CustomEvent('otpad-tab', { detail: ime }));
  }
  TABOVI.forEach(function (t) { $('tab-' + t).addEventListener('click', function () { tabPrebaci(t); }); });
  window.OTPAD = { $: $, el: el, isprazni: isprazni, api: api, poruka: poruka, zauzet: zauzet, vozilo: vozilo,
                   cijena: cijena, tab: tabPrebaci };

  // ---------- TRAŽI ----------
  function prikaziRezultate(d) {
    var r = $('rezultati'); isprazni(r);
    if (d.dijelovi.length) {
      r.appendChild(el('h2', { class: 'naslov-odjeljka' }, 'Dijelovi s tim brojem'));
      d.dijelovi.forEach(function (dio) {
        var kartica = el('div', { class: 'kartica' }, el('h3', null, dio.naziv));
        var cipovi = el('div', { class: 'cipovi' });
        dio.brojevi.forEach(function (b) {
          cipovi.appendChild(el('span', { class: 'cip' }, b.broj + ' · ' + b.vrsta + (b.proizvodjac ? ' · ' + b.proizvodjac : '')));
        });
        kartica.appendChild(cipovi);
        if (dio.vozila.length) {
          kartica.appendChild(el('p', { class: 'sitno' }, 'Stane na:'));
          var ul = el('ul');
          dio.vozila.forEach(function (v) { ul.appendChild(el('li', null, vozilo(v))); });
          kartica.appendChild(ul);
        }
        if (dio.na_zalihi > 0) {
          kartica.appendChild(el('p', null, el('span', { class: 'znak ima' }, 'Na zalihi: ' + dio.na_zalihi)));
          var zul = el('ul');
          dio.zaliha.forEach(function (z) {
            zul.appendChild(el('li', null, [z.polica ? 'polica ' + z.polica : 'polica nije upisana',
              'stanje ' + z.stanje, z.cijena != null ? cijena(z.cijena) : 'bez cijene'].join(' · ')));
          });
          kartica.appendChild(zul);
        } else {
          kartica.appendChild(el('p', null, el('span', { class: 'znak nema' }, 'Nemamo na zalihi')));
        }
        r.appendChild(kartica);
      });
    }
    if (d.vozila.length) {
      r.appendChild(el('h2', { class: 'naslov-odjeljka' }, 'Auta koja odgovaraju' + (d.godina ? ' (godina ' + d.godina + ')' : '')));
      var k = el('div', { class: 'kartica' }), ul2 = el('ul');
      d.vozila.forEach(function (v) { ul2.appendChild(el('li', null, vozilo(v))); });
      k.appendChild(ul2);
      if (d.vozila_ima_jos) k.appendChild(el('p', { class: 'sitno' }, 'Prikazano je prvih 40. Upiši točnije (npr. dodaj model ili godinu).'));
      r.appendChild(k);
    }
  }

  $('forma-trazi').addEventListener('submit', function (e) {
    e.preventDefault();
    var q = $('q').value.trim(), por = $('poruka-trazi');
    if (q.length < 2) { poruka(por, 'greska', 'Upiši barem 2 znaka.'); $('q').focus(); return; }
    poruka(por, 'info', '');
    zauzet($('btn-trazi'), 'Tražim…', function () {
      return api('GET', '/api/trazi?q=' + encodeURIComponent(q));
    }).then(function (odg) {
      isprazni($('rezultati'));
      if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
      var d = odg.data;
      if (!d.dijelovi.length && !d.vozila.length) {
        poruka(por, 'info', 'Ništa nije nađeno. Provjeri je li broj točno upisan (razmaci i crtice nisu važni) ili upiši kraće.');
        return;
      }
      var n = d.dijelovi.length + d.vozila.length;
      poruka(por, 'ok', 'Nađeno: ' + (d.dijelovi.length ? d.dijelovi.length + ' dio/dijelova' : '') +
        (d.dijelovi.length && d.vozila.length ? ' i ' : '') + (d.vozila.length ? d.vozila.length + ' auta' : '') + '.');
      prikaziRezultate(d);
    });
  });

  // ---------- UNOS: auti ----------
  function ucitajAute(odaberi) {
    return api('GET', '/api/otpad-vozila').then(function (odg) {
      var s = $('auto'), staro = odaberi || s.value;
      isprazni(s);
      s.appendChild(el('option', { value: '' }, '— odaberi auto —'));
      if (!odg.ok) { poruka($('poruka-unos'), 'greska', odg.data.greska); return; }
      odg.data.vozila.forEach(function (v) {
        s.appendChild(el('option', { value: v.id },
          vozilo(v) + ' · ' + (v.vin ? 'VIN ' + v.vin : 'bez VIN-a') + (v.km ? ' · ' + v.km + ' km' : '')));
      });
      if (staro) s.value = String(staro);
    });
  }
  function ucitajNazive() {
    return api('GET', '/api/nazivi').then(function (odg) {
      var dl = $('nazivi'); isprazni(dl);
      if (odg.ok) odg.data.nazivi.forEach(function (n) { dl.appendChild(el('option', { value: n })); });
    });
  }
  function ucitajZadnje() {
    return api('GET', '/api/zadnji').then(function (odg) {
      var z = $('zadnji'); isprazni(z);
      if (!odg.ok) { z.appendChild(el('p', { class: 'poruka greska' }, odg.data.greska)); return; }
      if (!odg.data.dijelovi.length) { z.appendChild(el('p', { class: 'sitno' }, 'Još ništa nije uneseno.')); return; }
      odg.data.dijelovi.forEach(function (d) {
        z.appendChild(el('div', { class: 'kartica' },
          el('b', null, d.naziv + (d.broj ? ' · ' + d.broj : '')),
          el('div', { class: 'sitno' }, [d.auto, d.polica ? 'polica ' + d.polica : null, 'stanje ' + d.stanje,
            d.cijena != null ? cijena(d.cijena) : null, d.status === 'PRODAN' ? 'PRODANO' : null].filter(Boolean).join(' · '))));
      });
    });
  }
  function osvjeziUnos() { ucitajAute(); ucitajNazive(); ucitajZadnje(); }

  $('btn-novi-auto').addEventListener('click', function () {
    var f = $('novi-auto'), otvoren = f.hidden;
    f.hidden = !otvoren;
    this.setAttribute('aria-expanded', otvoren ? 'true' : 'false');
    if (otvoren) $('tip-q').focus();
  });

  $('btn-tip').addEventListener('click', function () {
    var q = $('tip-q').value.trim(), por = $('poruka-auto'), lista = $('tip-lista');
    isprazni(lista);
    if (q.length < 2) { poruka(por, 'greska', 'Upiši marku i model (npr. Focus 2013).'); $('tip-q').focus(); return; }
    poruka(por, 'info', '');
    zauzet(this, 'Tražim…', function () { return api('GET', '/api/trazi?q=' + encodeURIComponent(q)); })
      .then(function (odg) {
        if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
        var v = odg.data.vozila;
        if (!v.length) { poruka(por, 'info', 'Nema takve vrste auta. Probaj samo marku i model, bez godine.'); return; }
        poruka(por, 'info', 'Klikni na točnu vrstu auta (' + v.length + (odg.data.vozila_ima_jos ? '+' : '') + ' nađeno).');
        v.forEach(function (x) {
          var lab = el('label', { class: 'radio-opcija' },
            el('input', { type: 'radio', name: 'tip', value: x.id }), el('span', null, vozilo(x)));
          lista.appendChild(lab);
        });
      });
  });

  $('btn-spremi-auto').addEventListener('click', function () {
    var por = $('poruka-auto'), izabran = document.querySelector('input[name="tip"]:checked');
    if (!izabran) { poruka(por, 'greska', 'Prvo odaberi vrstu auta s popisa (klikni na točan red).'); return; }
    zauzet(this, 'Spremam auto…', function () {
      return api('POST', '/api/otpad-vozila', {
        vozilo_tip_id: izabran.value, vin: $('auto-vin').value, km: $('auto-km').value });
    }).then(function (odg) {
      if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
      poruka(por, 'ok', odg.data.poruka);
      $('auto-vin').value = ''; $('auto-km').value = ''; $('tip-q').value = ''; isprazni($('tip-lista'));
      $('novi-auto').hidden = true; $('btn-novi-auto').setAttribute('aria-expanded', 'false');
      ucitajAute(odg.data.id).then(function () {
        poruka($('poruka-unos'), 'ok', 'Auto je dodan i odabran. Sad unesi dio.');
        $('dio-broj').focus();
      });
    });
  });

  // ---------- UNOS: prepoznavanje broja ----------
  function ocistiPrepoznato() {
    stanje.dioId = null; stanje.prepoznatoBroj = '';
    $('dio-naziv').readOnly = false;
    $('prepoznato').hidden = true; isprazni($('prepoznato'));
  }
  $('dio-broj').addEventListener('input', function () {
    if (stanje.dioId && this.value !== stanje.prepoznatoBroj) { ocistiPrepoznato(); }
  });
  $('dio-broj').addEventListener('change', function () {
    var broj = this.value.trim();
    if (broj.replace(/[^0-9A-Za-z]/g, '').length < 3) { ocistiPrepoznato(); return; }
    api('GET', '/api/trazi?q=' + encodeURIComponent(broj)).then(function (odg) {
      if (!odg.ok) { poruka($('poruka-unos'), 'greska', odg.data.greska); return; }
      var d = odg.data.dijelovi;
      if (d.length !== 1) { ocistiPrepoznato(); return; }
      var dio = d[0];
      stanje.dioId = dio.dio_id; stanje.prepoznatoBroj = broj;
      $('dio-naziv').value = dio.naziv; $('dio-naziv').readOnly = true;
      var p = $('prepoznato'); isprazni(p);
      p.appendChild(el('b', null, 'Prepoznato: ' + dio.naziv + '.'));
      if (dio.vozila.length) p.appendChild(el('div', null, 'Stane na: ' + dio.vozila.slice(0, 4).map(vozilo).join('; ') +
        (dio.vozila.length > 4 ? ' …' : '')));
      var ne = el('button', { class: 'gumb', type: 'button' }, 'To nije taj dio');
      ne.addEventListener('click', function () { ocistiPrepoznato(); $('dio-naziv').value = ''; $('dio-naziv').focus(); });
      p.appendChild(ne);
      p.hidden = false;
    });
  });

  // ---------- UNOS: spremanje dijela ----------
  function resetDio() {
    ['dio-broj', 'dio-naziv', 'polica', 'cijena'].forEach(function (i) { $(i).value = ''; });
    var r = document.querySelector('input[name="stanje"]:checked'); if (r) r.checked = false;
    ocistiPrepoznato(); $('duplikat').hidden = true;
  }

  function spremiDio(dopustiDuplikat) {
    var por = $('poruka-unos'), auto = $('auto').value;
    poruka(por, '', ''); $('duplikat').hidden = true;
    if (!auto) { poruka(por, 'greska', 'Prvo odaberi auto s kojeg je dio skinut (korak 1).'); $('auto').focus(); return; }
    var naziv = $('dio-naziv').value.trim();
    if (!stanje.dioId && naziv.length < 2) { poruka(por, 'greska', 'Upiši naziv dijela (korak 2).'); $('dio-naziv').focus(); return; }
    var st = document.querySelector('input[name="stanje"]:checked');
    if (!st) { poruka(por, 'greska', 'Odaberi stanje dijela: A, B, C ili D (korak 3).'); document.querySelector('input[name="stanje"]').focus(); return; }
    zauzet($('btn-spremi'), 'Spremam…', function () {
      return api('POST', '/api/otpad-dijelovi', {
        otpad_vozilo_id: auto, dio_id: stanje.dioId, naziv: naziv, broj_na_dijelu: $('dio-broj').value,
        polica: $('polica').value, stanje: st.value, cijena: $('cijena').value,
        dopusti_duplikat: !!dopustiDuplikat });
    }).then(function (odg) {
      if (odg.status === 409 && odg.data.duplikat) {
        $('duplikat-tekst').textContent = odg.data.greska; $('duplikat').hidden = false;
        $('btn-duplikat').focus(); return;
      }
      if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
      var d = odg.data;
      poruka(por, 'ok', 'Spremljeno: ' + d.naziv + (d.broj_norm ? ' (' + d.broj_norm + ')' : '') +
        (($('polica').value.trim()) ? ', polica ' + $('polica').value.trim() : '') + '. Možeš unijeti sljedeći dio s istog auta.');
      resetDio(); ucitajZadnje(); ucitajNazive(); $('dio-broj').focus();
    });
  }
  $('btn-spremi').addEventListener('click', function () { spremiDio(false); });
  $('btn-duplikat').addEventListener('click', function () { spremiDio(true); });

  // ---------- početak ----------
  $('q').focus();
}());
