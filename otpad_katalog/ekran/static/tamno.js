(function () {
  'use strict';
  // Tamni dio: novi dio, dijelovi u radu (slike, pranje, test, pakiranje, pretinac, prodaja), stalaža.
  var O = window.OTPAD, $ = O.$, el = O.el, api = O.api, poruka = O.poruka, zauzet = O.zauzet, isprazni = O.isprazni;

  var VRSTE = { DIO: 'Slike dijela', POSLIJE_PRANJA: 'Slika poslije pranja', PAKET: 'Slika zapakiranog dijela', POLICA: 'Slika dijela u pretincu' };
  var STATUS = { RODEN: 'Unesen', PREDRADNJE: 'U predradnjama', NA_STALAZI: 'Na stalaži', NA_ZALIHI: 'U prodaji',
                 REZERVIRAN: 'Rezerviran', PRODAN: 'Prodan', ISPORUCEN: 'Isporučen', POVRAT_ZATRAZEN: 'Povrat zatražen', SKART: 'Škart' };
  var RAZREDI = [['POTROSAC_12M', 'Potrošač, 12 mjeseci (zadano za rabljeno)'], ['POTROSAC_24M', 'Potrošač, 24 mjeseca'],
                 ['PRAVNA_BEZ', 'Samo pravne osobe, bez jamstva']];
  var JAVNE = {};          // dio_id -> { slika_id: true }, izbor javnih slika (zadano sve slike dijela)
  var otvoren = null;
  var obavijest = null;    // potvrda ili greška koja mora preživjeti ponovno iscrtavanje kartice
  function obavijesti(vrsta, tekst) { obavijest = { vrsta: vrsta, tekst: tekst }; }

  function chip(tekst, vrsta) { return el('span', { class: 'status' + (vrsta ? ' ' + vrsta : '') }, tekst); }
  function pretinacChip(a) { return a ? chip('pretinac ' + a, 'ok') : chip('bez pretinca', 'up'); }

  // ---------- NOVI DIO ----------
  var prepoznatiDio = null;
  function ucitajAute() {
    return api('GET', '/api/otpad-vozila').then(function (odg) {
      var s = $('nd-auto'), staro = s.value; isprazni(s);
      s.appendChild(el('option', { value: '' }, '— odaberi auto —'));
      if (!odg.ok) { poruka($('nd-poruka'), 'greska', odg.data.greska); return; }
      odg.data.vozila.forEach(function (v) {
        s.appendChild(el('option', { value: v.id }, O.vozilo(v) + ' · ' + (v.vin ? 'VIN ' + v.vin : 'bez VIN-a')));
      });
      if (staro) s.value = staro;
    });
  }
  function ucitajNazive() {
    return api('GET', '/api/nazivi').then(function (odg) {
      var dl = $('nd-nazivi'); isprazni(dl);
      if (odg.ok) odg.data.nazivi.forEach(function (n) { dl.appendChild(el('option', { value: n })); });
    });
  }
  function ocistiPrepoznato() {
    prepoznatiDio = null; $('nd-naziv').readOnly = false; $('nd-prepoznato').hidden = true; isprazni($('nd-prepoznato'));
  }
  $('nd-broj').addEventListener('change', function () {
    var broj = this.value.trim();
    if (broj.replace(/[^0-9A-Za-z]/g, '').length < 3) { ocistiPrepoznato(); return; }
    api('GET', '/api/trazi?q=' + encodeURIComponent(broj)).then(function (odg) {
      if (!odg.ok || odg.data.dijelovi.length !== 1) { ocistiPrepoznato(); return; }
      var d = odg.data.dijelovi[0];
      prepoznatiDio = d.dio_id; $('nd-naziv').value = d.naziv; $('nd-naziv').readOnly = true;
      var p = $('nd-prepoznato'); isprazni(p);
      p.appendChild(el('b', null, 'Prepoznato: ' + d.naziv + '.'));
      var ne = el('button', { class: 'gumb', type: 'button' }, 'To nije taj dio');
      ne.addEventListener('click', function () { ocistiPrepoznato(); $('nd-naziv').value = ''; $('nd-naziv').focus(); });
      p.appendChild(ne); p.hidden = false;
    });
  });
  $('nd-broj').addEventListener('input', function () { if (prepoznatiDio) ocistiPrepoznato(); });

  $('nd-rodi').addEventListener('click', function () {
    var por = $('nd-poruka'), auto = $('nd-auto').value;
    poruka(por, '', '');
    if (!auto) { poruka(por, 'greska', 'Prvo odaberi auto s kojeg je dio skinut (korak 1).'); $('nd-auto').focus(); return; }
    zauzet(this, 'Unosim dio…', function () {
      return api('POST', '/api/dio/rodi', { otpad_vozilo_id: auto, broj_na_dijelu: $('nd-broj').value,
        naziv: $('nd-naziv').value, dio_id: prepoznatiDio });
    }).then(function (odg) {
      if (odg.status === 409 && odg.data.duplikat) {
        if (!window.confirm(odg.data.greska)) { poruka(por, 'info', 'Unos je otkazan.'); return; }
        return api('POST', '/api/dio/rodi', { otpad_vozilo_id: auto, broj_na_dijelu: $('nd-broj').value,
          naziv: $('nd-naziv').value, dio_id: prepoznatiDio, dopusti_duplikat: true }).then(nakonRodenja);
      }
      return nakonRodenja(odg);
    });
  });
  function nakonRodenja(odg) {
    var por = $('nd-poruka');
    if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
    poruka(por, 'ok', odg.data.poruka);
    ['nd-broj', 'nd-naziv'].forEach(function (i) { $(i).value = ''; }); ocistiPrepoznato();
    O.tab('radu'); otvoriDio(odg.data.id);
  }

  // ---------- U RADU: popis ----------
  function checklistChipovi(c) {
    return [chip('slike ' + c.slika_dio + '/' + c.slika_dio_treba, c.slika_dio >= c.slika_dio_treba ? 'ok' : 'up'),
            chip(c.opran ? 'oprano' : 'nije oprano', c.opran ? 'ok' : 'up'),
            chip(c.test ? 'test ' + c.test : 'nije testirano', c.test === 'DRZI' ? 'ok' : (c.test === 'PAD' ? 'gr' : 'up')),
            chip(c.pakiran ? 'pakirano' : 'nije pakirano', c.pakiran ? 'ok' : 'up'), pretinacChip(c.lokacija)];
  }
  function ucitajRadu() {
    var por = $('radu-poruka');
    return api('GET', '/api/tamni').then(function (odg) {
      var l = $('radu-lista'); isprazni(l);
      if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
      if (!odg.data.dijelovi.length) { poruka(por, 'info', 'Nema dijelova u radu. Unesi novi dio u kartici „Novi dio“.'); return; }
      poruka(por, 'info', 'Klikni na dio da nastaviš (' + odg.data.dijelovi.length + ').');
      odg.data.dijelovi.forEach(function (d) {
        var gumb = el('button', { class: 'gumb', type: 'button' }, 'Otvori');
        gumb.addEventListener('click', function () { otvoriDio(d.id); });
        l.appendChild(el('div', { class: 'kartica' },
          el('h3', null, d.naziv + (d.broj ? ' · ' + d.broj : '')),
          el('div', { class: 'sitno' }, 'oznaka ' + d.token + ' · ' + (STATUS[d.status] || d.status)),
          el('div', { class: 'cipovi' }, checklistChipovi(d.checklist)), gumb));
      });
    });
  }
  $('dio-natrag').addEventListener('click', function () { zatvoriDio(); ucitajRadu(); });
  function zatvoriDio() { otvoren = null; $('dio-okvir').hidden = true; $('radu-lista-okvir').hidden = false; }

  // ---------- U RADU: kartica dijela ----------
  function otvoriDio(id) {
    otvoren = id;
    return api('GET', '/api/dio/' + id).then(function (odg) {
      $('radu-lista-okvir').hidden = true; $('dio-okvir').hidden = false;
      var k = $('dio-kartica'); isprazni(k);
      if (!odg.ok) { k.appendChild(el('p', { class: 'poruka greska', role: 'alert' }, odg.data.greska)); return; }
      prikaziDio(odg.data, k);
    });
  }
  function osvjezi() { return otvoren ? otvoriDio(otvoren) : Promise.resolve(); }

  function sekcija(naslov) {
    var por = el('p', { class: 'poruka', role: 'status', 'aria-live': 'polite' });
    var s = el('section', { class: 'odjeljak' }, el('h3', null, naslov));
    return { n: s, por: por };
  }

  // klijentsko smanjivanje: kraći prijenos i izbacuje EXIF (npr. GPS lokaciju) iz fotografije
  function smanji(file) {
    if (!window.createImageBitmap || !file.type || file.type.indexOf('image/') !== 0 || file.type === 'image/webp') return Promise.resolve(file);
    return createImageBitmap(file).then(function (bmp) {
      var f = Math.min(1, 2000 / Math.max(bmp.width, bmp.height)), c = document.createElement('canvas');
      c.width = Math.round(bmp.width * f); c.height = Math.round(bmp.height * f);
      c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
      return new Promise(function (res) { c.toBlob(function (b) { res(b || file); }, 'image/jpeg', 0.86); });
    }, function () { return file; });
  }

  function slikeSekcija(d, vrsta, trebaMin, ugnijezdi) {
    var S = sekcija(VRSTE[vrsta]), moje = d.slike.filter(function (s) { return s.vrsta === vrsta; });
    var kut = el('div', { class: 'slike' });
    moje.forEach(function (s) {
      var jed = el('div', { class: 'slika' }, el('img', { src: '/api/slika/' + s.id, alt: VRSTE[vrsta] + ' ' + s.id, width: 104, height: 104 }));
      if (vrsta === 'DIO' && d.status === 'NA_STALAZI') {
        var izbor = JAVNE[d.id] || (JAVNE[d.id] = {});
        if (!(s.id in izbor)) izbor[s.id] = true;
        var cb = el('input', { type: 'checkbox', id: 'javna-' + s.id });
        cb.checked = !!izbor[s.id];
        cb.addEventListener('change', function () { izbor[s.id] = cb.checked; });
        jed.appendChild(el('label', { for: 'javna-' + s.id }, cb, 'u oglasu'));
      }
      kut.appendChild(jed);
    });
    S.n.appendChild(el('p', { class: 'sitno' }, moje.length + (trebaMin ? ' od najmanje ' + trebaMin : '') + ' slika'));
    S.n.appendChild(kut);
    if (['RODEN', 'PREDRADNJE', 'NA_STALAZI', 'NA_ZALIHI'].indexOf(d.status) >= 0) {
      var ulaz = el('input', { type: 'file', accept: 'image/*', multiple: 'multiple', 'aria-label': 'Dodaj slike: ' + VRSTE[vrsta] });
      ulaz.addEventListener('change', function () {
        var datoteke = Array.prototype.slice.call(ulaz.files); if (!datoteke.length) return;
        ulaz.disabled = true; var n = 0, greske = [];
        poruka(S.por, 'info', 'Šaljem sliku 1 od ' + datoteke.length + '…');
        datoteke.reduce(function (lanac, f) {
          return lanac.then(function () { return smanji(f); }).then(function (b) {
            return api('POST', '/api/dio/' + d.id + '/slika', b, { 'X-Vrsta': vrsta });
          }).then(function (odg) {
            n += 1;
            if (!odg.ok) greske.push(odg.data.greska); else poruka(S.por, 'info', 'Poslano ' + n + ' od ' + datoteke.length + '…');
          });
        }, Promise.resolve()).then(function () {
          if (greske.length) obavijesti('greska', greske[0] + (greske.length > 1 ? ' (+' + (greske.length - 1) + ' grešaka)' : '') + (n - greske.length > 0 ? ' Ostale slike su spremljene.' : ''));
          else obavijesti('ok', datoteke.length === 1 ? 'Slika je spremljena.' : 'Slike su spremljene (' + datoteke.length + ').');
          return osvjezi();
        });
      });
      S.n.appendChild(ulaz);
    }
    S.n.appendChild(S.por);
    if (ugnijezdi) S.n.className = 'ugnijezdeno';
    return S.n;
  }

  function radnja(S, gumb, tekst, url, tijelo, dalje) {
    gumb.addEventListener('click', function () {
      poruka(S.por, '', '');
      zauzet(gumb, tekst, function () { return api('POST', url, tijelo()); }).then(function (odg) {
        if (!odg.ok) {
          poruka(S.por, 'greska', odg.data.greska);
          if (odg.data.razlozi) { var ul = el('ul', { class: 'razlozi' }); odg.data.razlozi.forEach(function (r) { ul.appendChild(el('li', null, r)); }); S.por.appendChild(ul); }
          return;
        }
        obavijesti('ok', odg.data.poruka || 'Spremljeno.');
        osvjezi().then(function () { if (dalje) dalje(odg.data); });
      });
    });
  }

  function prikaziDio(d, k) {
    var c = d.checklist, tamno = ['RODEN', 'PREDRADNJE', 'NA_STALAZI'].indexOf(d.status) >= 0;
    if (obavijest) {
      k.appendChild(el('p', { class: 'poruka ' + obavijest.vrsta, role: obavijest.vrsta === 'greska' ? 'alert' : 'status' }, obavijest.tekst));
      obavijest = null;
    }
    k.appendChild(el('div', { class: 'kartica' }, el('h3', null, d.naziv + (d.broj ? ' · ' + d.broj : '')),
      el('div', { class: 'sitno' }, [d.auto, 'oznaka ' + d.token].filter(Boolean).join(' · ')),
      el('div', { class: 'cipovi' }, chip(STATUS[d.status] || d.status, d.status === 'NA_ZALIHI' ? 'ok' : (d.status === 'SKART' ? 'gr' : '')),
        checklistChipovi(c))));
    if (d.status === 'SKART') { k.appendChild(el('p', { class: 'poruka greska' }, 'Ovaj dio je u škartu (test nije prošao).')); }

    // 1. slikanje
    k.appendChild(slikeSekcija(d, 'DIO', c.slika_dio_treba));

    // 2. pranje
    var P = sekcija('Pranje');
    P.n.appendChild(el('p', null, c.opran ? chip('oprano ✓', 'ok') : chip('nije oprano', 'up')));
    P.n.appendChild(slikeSekcija(d, 'POSLIJE_PRANJA', 0, true));
    if (tamno && !c.opran) {
      var bp = el('button', { class: 'gumb gumb-glavni', type: 'button' }, 'Označi oprano');
      if (!c.slika_pranje) { bp.disabled = true; P.n.appendChild(el('p', { class: 'pomoc' }, 'Prvo slikaj dio nakon pranja (gore).')); }
      radnja(P, bp, 'Spremam…', '/api/dio/' + d.id + '/predradnja', function () { return { vrsta: 'OPRAN' }; });
      P.n.appendChild(bp);
    }
    P.n.appendChild(P.por); k.appendChild(P.n);

    // 3. test
    var T = sekcija('Test');
    T.n.appendChild(el('p', null, c.test ? chip('zadnji test: ' + c.test, c.test === 'DRZI' ? 'ok' : (c.test === 'PAD' ? 'gr' : 'up')) : chip('nije testirano', 'up')));
    if (tamno) {
      T.n.appendChild(el('label', { class: 'oznaka', for: 'test-nap' }, 'Bilješka testa (nije obavezno)'));
      var nap = el('input', { id: 'test-nap', maxlength: 200, autocomplete: 'off' }); T.n.appendChild(nap);
      var red = el('div', { class: 'red' });
      [['DRZI', 'Radi (DRŽI)'], ['NEPOZNATO', 'Ne znam'], ['PAD', 'Ne radi (PAD → škart)']].forEach(function (x) {
        var g = el('button', { class: 'gumb' + (x[0] === 'DRZI' ? ' gumb-glavni' : ''), type: 'button' }, x[1]);
        radnja(T, g, 'Spremam…', '/api/dio/' + d.id + '/predradnja', function () { return { vrsta: 'TESTIRAN', stanje: x[0], napomena: nap.value }; });
        red.appendChild(g);
      });
      T.n.appendChild(red);
    }
    T.n.appendChild(T.por); k.appendChild(T.n);

    // 4. pakiranje
    var Q = sekcija('Pakiranje');
    Q.n.appendChild(el('p', null, c.pakiran ? chip('pakirano ✓', 'ok') : chip('nije pakirano', 'up')));
    Q.n.appendChild(slikeSekcija(d, 'PAKET', 0, true));
    if (tamno && !c.pakiran) {
      Q.n.appendChild(el('div', { class: 'dvije' },
        el('div', null, el('label', { class: 'oznaka', for: 'pak-dim' }, 'Dimenzije u cm'), el('input', { id: 'pak-dim', placeholder: 'npr. 30x20x15', autocomplete: 'off' })),
        el('div', null, el('label', { class: 'oznaka', for: 'pak-tez' }, 'Težina u gramima'), el('input', { id: 'pak-tez', inputmode: 'numeric', placeholder: 'npr. 3200', autocomplete: 'off' }))));
      var bq = el('button', { class: 'gumb gumb-glavni', type: 'button' }, 'Upiši pakiranje');
      if (!c.slika_paket) { bq.disabled = true; Q.n.appendChild(el('p', { class: 'pomoc' }, 'Prvo slikaj zapakirani dio (gore).')); }
      radnja(Q, bq, 'Spremam…', '/api/dio/' + d.id + '/predradnja', function () {
        return { vrsta: 'PAKIRAN', dimenzije_cm: $('pak-dim').value, tezina_g: $('pak-tez').value }; });
      Q.n.appendChild(bq);
    }
    Q.n.appendChild(Q.por); k.appendChild(Q.n);

    // 5. pretinac
    var R = sekcija('Pretinac na stalaži');
    R.n.appendChild(el('p', null, pretinacChip(d.pretinac)));
    if (['RODEN', 'PREDRADNJE', 'NA_STALAZI', 'NA_ZALIHI'].indexOf(d.status) >= 0) {
      var sel = el('select', { id: 'pret-sel', 'aria-label': 'Pretinac' }); R.n.appendChild(sel);
      sel.appendChild(el('option', { value: '' }, '— odaberi pretinac —'));
      api('GET', '/api/pretinci').then(function (o) {
        if (!o.ok) { poruka(R.por, 'greska', o.data.greska); return; }
        if (!o.data.pretinci.length) { poruka(R.por, 'info', 'Još nema pretinaca. Dodaj ih u kartici „Stalaža“.'); return; }
        o.data.pretinci.forEach(function (p) { sel.appendChild(el('option', { value: p.adresa }, p.adresa + ' (' + p.dijelova + ')')); });
        if (d.pretinac) sel.value = d.pretinac;
      });
      var br = el('button', { class: 'gumb gumb-glavni', type: 'button' }, d.pretinac ? 'Premjesti' : 'Spremi u pretinac');
      radnja(R, br, 'Spremam…', '/api/dio/' + d.id + '/spremi', function () { return { adresa: sel.value }; });
      R.n.appendChild(br);
    }
    R.n.appendChild(R.por); k.appendChild(R.n);
    if (d.pretinac) k.appendChild(slikeSekcija(d, 'POLICA'));

    // 6. vrata prema svjetlu
    if (d.status === 'NA_STALAZI') {
      var V = sekcija('Stavi u prodaju');
      V.n.appendChild(el('p', { class: 'pomoc' }, 'Dio izlazi u webshop tek kad stroj provjeri: najmanje ' + c.slika_dio_treba + ' slike, test DRŽI, pakiranje, pretinac, cijena, jamstvo i bar jedna slika za oglas (kvačica „u oglasu“ gore).'));
      V.n.appendChild(el('label', { class: 'oznaka', for: 'v-cijena' }, 'Cijena u €'));
      V.n.appendChild(el('input', { id: 'v-cijena', inputmode: 'decimal', placeholder: 'npr. 45 ili 45,50', autocomplete: 'off' }));
      V.n.appendChild(el('label', { class: 'oznaka', for: 'v-razred' }, 'Jamstvo'));
      var rs = el('select', { id: 'v-razred' }); rs.appendChild(el('option', { value: '' }, '— odaberi —'));
      RAZREDI.forEach(function (r) { rs.appendChild(el('option', { value: r[0] }, r[1])); }); V.n.appendChild(rs);
      var bv = el('button', { class: 'gumb gumb-glavni gumb-velik', type: 'button' }, 'Stavi u prodaju');
      radnja(V, bv, 'Provjeravam…', '/api/dio/' + d.id + '/prodaja', function () {
        var izbor = JAVNE[d.id] || {};
        return { cijena: $('v-cijena').value, razred_jamstva: $('v-razred').value,
                 javne_slike: Object.keys(izbor).filter(function (x) { return izbor[x]; }) };
      }, function (r) { poruka($('radu-poruka'), 'ok', r.poruka); });
      V.n.appendChild(bv); V.n.appendChild(V.por); k.appendChild(V.n);
    } else if (d.status === 'NA_ZALIHI') {
      k.appendChild(el('p', { class: 'poruka ok' }, 'Dio je u prodaji' + (d.cijena_centi ? ' za ' + O.cijena((d.cijena_centi / 100).toFixed(2)) : '') + '.'));
    }

    // povijest (što je rađeno)
    var ul = el('ul', { class: 'tablica-dnevnika' });
    d.povijest.forEach(function (p) { ul.appendChild(el('li', null, p.vrsta.toLowerCase().replace(/_/g, ' ') + ' · ' + String(p.vrijeme).slice(0, 16).replace('T', ' '))); });
    k.appendChild(el('details', null, el('summary', null, 'Što je rađeno s ovim dijelom'), ul));
  }

  // ---------- STALAŽA ----------
  function ucitajPretince() {
    return api('GET', '/api/pretinci').then(function (odg) {
      var l = $('pretinci-lista'); isprazni(l);
      if (!odg.ok) { poruka($('pr-poruka'), 'greska', odg.data.greska); return; }
      if (!odg.data.pretinci.length) { l.appendChild(el('p', { class: 'sitno' }, 'Još nema pretinaca.')); return; }
      odg.data.pretinci.forEach(function (p) {
        var g = el('button', { class: 'cip-gumb', type: 'button' }, p.adresa + ' · ' + p.dijelova);
        g.addEventListener('click', function () { $('nadji-q').value = p.adresa; traziStalaza(); });
        l.appendChild(g);
      });
    });
  }
  function obilazakForma(d) {
    var S = el('section', { class: 'odjeljak' }, el('h3', null, 'Obilazak pretinca ' + d.adresa));
    S.appendChild(el('p', { class: 'pomoc' }, 'Označi što stvarno vidiš u pretincu. Što ne označiš, upisuje se da nedostaje.'));
    var kutije = [];
    d.dijelovi.forEach(function (x) {
      var cb = el('input', { type: 'checkbox', id: 'ob-' + x.id });
      kutije.push([x, cb]);
      S.appendChild(el('label', { class: 'radio-opcija', for: 'ob-' + x.id }, cb,
        el('span', null, x.naziv + (x.broj ? ' · ' + x.broj : '') + ' · ' + x.token)));
    });
    if (!d.dijelovi.length) S.appendChild(el('p', { class: 'sitno' }, 'Prema evidenciji pretinac je prazan.'));
    S.appendChild(el('label', { class: 'oznaka', for: 'ob-viska' }, 'Višak: oznaka dijela koji je ovdje, a nije na popisu (nije obavezno)'));
    var vi = el('input', { id: 'ob-viska', maxlength: 16, autocomplete: 'off', spellcheck: 'false' });
    S.appendChild(vi);
    var por = el('p', { class: 'poruka', role: 'status', 'aria-live': 'polite' }), detalji = el('div');
    var g = el('button', { class: 'gumb gumb-glavni gumb-velik', type: 'button' }, 'Završi obilazak');
    g.addEventListener('click', function () {
      poruka(por, '', ''); isprazni(detalji);
      zauzet(g, 'Spremam…', function () {
        return api('POST', '/api/pretinac/' + d.adresa + '/obilazak', {
          nadjeni: kutije.filter(function (k) { return k[1].checked; }).map(function (k) { return k[0].id; }),
          viska: vi.value.trim() ? [vi.value.trim()] : [] });
      }).then(function (odg) {
        if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
        var r = odg.data, sve = !r.nedostaje.length && !r.viska.length && !r.nepoznato.length;
        poruka(por, sve ? 'ok' : 'info', r.poruka);
        var ul = el('ul', { class: 'razlozi' });
        r.nedostaje.forEach(function (id) {
          var x = d.dijelovi.filter(function (y) { return y.id === id; })[0];
          ul.appendChild(el('li', null, 'Nedostaje: ' + (x ? x.naziv + ' · ' + x.token : 'dio ' + id)));
        });
        r.viska.forEach(function (v) { ul.appendChild(el('li', null, 'Višak: dio ' + v.id + ' vodi se u ' + (v.pretinac || 'nijednom pretincu') + '. Premjesti ga u kartici dijela.')); });
        r.nepoznato.forEach(function (t) { ul.appendChild(el('li', null, 'Nepoznata oznaka: ' + t)); });
        if (ul.childNodes.length) detalji.appendChild(ul);
      });
    });
    S.appendChild(g); S.appendChild(por); S.appendChild(detalji);
    return S;
  }
  function prikaziNadji(d) {
    var r = $('nadji-rez'); isprazni(r);
    function dioKartica(x) {
      var g = el('button', { class: 'gumb', type: 'button' }, 'Otvori');
      g.addEventListener('click', function () { O.tab('radu'); otvoriDio(x.id); });
      return el('div', { class: 'kartica' }, el('h3', null, x.naziv + (x.broj ? ' · ' + x.broj : '')),
        el('div', { class: 'sitno' }, 'oznaka ' + x.token + ' · ' + (STATUS[x.status] || x.status)),
        el('div', { class: 'cipovi' }, pretinacChip(x.pretinac)), g);
    }
    if (d.vrsta === 'pretinac') {
      r.appendChild(el('h2', { class: 'naslov-odjeljka' }, 'Pretinac ' + d.adresa));
      if (!d.dijelovi.length) r.appendChild(el('p', { class: 'sitno' }, 'Pretinac je prazan.'));
      d.dijelovi.forEach(function (x) { r.appendChild(dioKartica(x)); });
      r.appendChild(obilazakForma(d));
    } else if (d.vrsta === 'dio') { r.appendChild(dioKartica({ id: d.dio.id, naziv: d.dio.naziv, broj: d.dio.broj, token: d.dio.token, status: d.dio.status, pretinac: d.dio.pretinac })); }
    else if (d.vrsta === 'dijelovi') { d.dijelovi.forEach(function (x) { r.appendChild(dioKartica(x)); }); }
  }
  function traziStalaza() {
    var q = $('nadji-q').value.trim(), por = $('nadji-poruka');
    if (q.length < 2) { poruka(por, 'greska', 'Upiši barem 2 znaka.'); $('nadji-q').focus(); return; }
    poruka(por, 'info', '');
    zauzet($('btn-nadji'), 'Tražim…', function () { return api('GET', '/api/nadji?q=' + encodeURIComponent(q)); }).then(function (odg) {
      isprazni($('nadji-rez'));
      if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
      if (odg.data.vrsta === 'nista') { poruka(por, 'info', 'Ništa nije nađeno. Provjeri adresu pretinca, oznaku ili broj.'); return; }
      poruka(por, 'ok', 'Nađeno.'); prikaziNadji(odg.data);
    });
  }
  $('forma-nadji').addEventListener('submit', function (e) { e.preventDefault(); traziStalaza(); });
  $('pr-dodaj').addEventListener('click', function () {
    var por = $('pr-poruka');
    zauzet(this, 'Dodajem…', function () {
      return api('POST', '/api/pretinci', { regal: $('pr-regal').value, polica: $('pr-polica').value, pretinaca: $('pr-n').value });
    }).then(function (odg) {
      if (!odg.ok) { poruka(por, 'greska', odg.data.greska); return; }
      poruka(por, 'ok', odg.data.poruka); ucitajPretince();
    });
  });

  // ---------- kartice ----------
  document.addEventListener('otpad-tab', function (e) {
    if (e.detail === 'novi') { ucitajAute(); ucitajNazive(); $('nd-auto').focus(); }
    if (e.detail === 'radu') { if (otvoren) osvjezi(); else ucitajRadu(); }
    if (e.detail === 'stalaza') { ucitajPretince(); $('nadji-q').focus(); }
  });
  window.OTPAD.otvoriDio = otvoriDio;
}());
