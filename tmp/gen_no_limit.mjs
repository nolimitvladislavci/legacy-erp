import { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType, LevelFormat } from '/tmp/node_modules/docx/dist/index.js';
import fs from 'fs';

const UDRUGA = 'NO LIMIT';
const ADRESA = 'Kr. Tomislava 291, 31404 Vladislavci';
const DATUM = '28. ozujka 2026.';
const DATUM_K = '28.03.2026.';
const P1 = { ime: 'Ivan Brtan', oib: '70086599476', dob: '18.09.1966.', adresa: 'Kalnicka 19, 31000 Cepin' };
const P2 = { ime: 'Kruljac Ivica', oib: '82540277049', dob: '-', adresa: 'Kr. Tomislava 291, 31404 Vladislavci' };
const P3 = { ime: 'Antonio Brtan', oib: '28907401487', dob: '12.02.2001.', adresa: 'Grabenstrasse 29E, Gartringen, DE' };

const b1 = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const brd = { top: b1, bottom: b1, left: b1, right: b1 };
const nb = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const nob = { top: nb, bottom: nb, left: nb, right: nb };
const mc = { top: 90, bottom: 90, left: 130, right: 130 };

const num = { config: [
  { reference: 'bul', levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  { reference: 'num', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  { reference: 'cln', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: 'Clanak %1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 0 } } } }] },
]};

const sty = {
  default: { document: { run: { font: 'Arial', size: 22 } } },
  paragraphStyles: [
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 26, bold: true, font: 'Arial', color: '1A3A6B' }, paragraph: { spacing: { before: 300, after: 150 }, outlineLevel: 0 } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 23, bold: true, font: 'Arial' }, paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
  ]
};

const pg = (t, opts = {}) => new Paragraph({ spacing: { after: 140 }, alignment: opts.c ? AlignmentType.CENTER : (opts.j ? AlignmentType.JUSTIFIED : AlignmentType.LEFT), children: [new TextRun({ text: t, font: 'Arial', size: 22, bold: !!opts.bold, italics: !!opts.i })] });
const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 300, after: 150 }, children: [new TextRun({ text: t, bold: true, size: 26, font: 'Arial', color: '1A3A6B' })] });
const h2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 100 }, children: [new TextRun({ text: t, bold: true, size: 23, font: 'Arial' })] });
const br = () => new Paragraph({ children: [new TextRun({ text: '', font: 'Arial', size: 22 })] });
const bul = t => new Paragraph({ numbering: { reference: 'bul', level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: t, font: 'Arial', size: 22 })] });
const nump = t => new Paragraph({ numbering: { reference: 'num', level: 0 }, spacing: { after: 80 }, children: [new TextRun({ text: t, font: 'Arial', size: 22 })] });
const cln = t => new Paragraph({ numbering: { reference: 'cln', level: 0 }, spacing: { before: 200, after: 100 }, children: [new TextRun({ text: t, bold: true, font: 'Arial', size: 22 })] });

const hdr = (title, sub) => [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: `UDRUGA ${UDRUGA}`, bold: true, size: 34, font: 'Arial', color: '1A3A6B' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: ADRESA, font: 'Arial', size: 19, color: '666666' })] }),
  new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: '1A3A6B', space: 1 } }, spacing: { after: 280 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 }, children: [new TextRun({ text: title, bold: true, size: 30, font: 'Arial', color: '1A3A6B' })] }),
  sub ? new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [new TextRun({ text: sub, font: 'Arial', size: 21, italics: true })] }) : br(),
];

const pgProp = { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1800 } } };

const decisBox = t => new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 1, color: 'AAAAAA' }, bottom: { style: BorderStyle.SINGLE, size: 1, color: 'AAAAAA' } }, spacing: { before: 100, after: 100 }, children: [new TextRun({ text: t, bold: true, font: 'Arial', size: 22, color: '1A3A6B' })] });

// STATUT
const statut = new Document({ numbering: num, styles: sty, sections: [{ properties: pgProp, children: [
  ...hdr('S T A T U T', `Udruge "${UDRUGA}"`),
  h1('I. OPCE ODREDBE'),
  cln('Naziv i sjediste'),
  pg(`Naziv: UDRUGA ${UDRUGA}. Sjediste: ${ADRESA}. Udruga djeluje na podrucju RH i medunarodnoj razini.`, { j: true }),
  br(), cln('Pravna osobnost'),
  pg(`Udruga ${UDRUGA} je pravna osoba upisana u Registar udruga RH. Zastupa je predsjednik.`, { j: true }),
  br(), cln('Pecat'),
  pg(`Okrugli pecat promjera 30 mm: UDRUGA ${UDRUGA} — Vladislavci.`, { j: true }),
  br(),
  h1('II. CILJEVI I DJELATNOSTI'),
  cln('Ciljevi udruge'),
  bul('Promicanje i zastita prava gradana na koristenje gotovog novca kao zakonskog sredstva placanja.'),
  bul('Edukacija javnosti o financijskoj privatnosti, zastiti osobnih podataka i sigurnosti u digitalnom okruzenju.'),
  bul('Razvoj i promicanje tehnoloskih rjesenja otvorenog koda (Open Source) koji podupiru decentralizaciju financijskih sustava.'),
  bul('Digitalno opismenjavanje gradana, obrtnika i poduzetnika o koristenju sigurnih informatickih sustava.'),
  bul('Savjetovanje u podrucju informatickih sustava, sigurnosti podataka i zastite privatnosti.'),
  bul('Zagovaranje zakonodavnih rjesenja koja stite pravo na gotovinsko placanje na razini RH i EU.'),
  br(), cln('Djelatnosti za ostvarenje ciljeva'),
  bul('Organiziranje seminara, radionica i okruglih stolova na teme financijske slobode i privatnosti.'),
  bul('Izdavacka djelatnost: prirucnici, e-knjige, tecajevi, webinari.'),
  bul('Razvoj softvera, web aplikacija i digitalnih alata.'),
  bul('Istrazivanje i pracenje propisa koji utjecu na pravo na gotovinska placanja.'),
  br(), cln('Gospodarske djelatnosti (cl. 31. Zakona o udrugama)'),
  bul('Prodaja vlastitih publikacija i edukativnih materijala.'),
  bul('Naplatni tecajevi, radionice i savjetodavne usluge.'),
  bul('Izrada i prodaja softvera te web rjesenja.'),
  bul('Tehnicko odrzavanje informaticke opreme i sustava.'),
  bul('Trgovina na malo informatickom opremom vezanom uz ciljeve udruge.'),
  pg('Dobit ostvarena gospodarskim djelatnostima koristi se iskljucivo za ostvarivanje ciljeva udruge.', { j: true }),
  br(),
  h1('III. CLANSTVO'),
  cln('Uvjeti i nacin uclanjivanja'),
  pg('Clanom moze postati svaka punoljetna fizicka ili pravna osoba koja prihvaca Statut i ciljeve. Maloljetne osobe uz pisanu suglasnost zakonskog zastupnika.', { j: true }),
  br(), cln('Prava i obveze clanova'),
  pg('Prava: sudjelovanje u radu, pravo biranja i biti biran, koristenje usluga. Obveze: placanje clanarine, aktivno sudjelovanje, cuvanje ugleda udruge.', { j: true }),
  br(), cln('Prestanak clanstva'),
  pg('Clanstvo prestaje: dobrovoljnim istupanjem, neplacanjem clanarine dulje od godinu dana, iskljucenjem zbog krsenja Statuta ili pravomonom osudom za kazneno djelo nespojivo s ciljevima.', { j: true }),
  br(),
  h1('IV. UPRAVLJANJE UDRUGOM'),
  cln('Tijela udruge'),
  nump('Skupstina udruge'), nump('Predsjednik udruge'), nump('Tajnik udruge'), nump('Nadzorni odbor (po odluci Skupstine)'),
  br(), cln('Skupstina'),
  pg('Skupstina je najvise tijelo upravljanja. Cine je svi punopravni clanovi. Redovita sjednica jedanput godisnje. Odluke natpolovi%nom veinom prisutnih.', { j: true }),
  pg('Nadleznost: donosi i mijenja Statut, usvaja program rada i financijski plan, bira i razrjesuje predsjednika, odlucuje o prestanku udruge.', { j: true }),
  br(), cln('Predsjednik'),
  pg(`Predsjednika bira Skupstina na mandat 4 godine. Zastupa udrugu, provodi odluke Skupstine, potpisuje akte. Predsjednik: ${P1.ime}.`, { j: true }),
  br(), cln('Tajnik'),
  pg(`Tajnika bira Skupstina na mandat 4 godine. Vodi administrativne poslove i zapisnike. Tajnik: ${P2.ime}.`, { j: true }),
  br(),
  h1('V. IMOVINA I FINANCIRANJE'),
  cln('Imovina udruge'),
  pg('Imovinu cine sredstva od clanarina, donacija, sponzorstava, prihoda od djelatnosti i potpora. Udruga vodi poslovne knjige sukladno propisima o racunovodstvu neprofitnih organizacija.', { j: true }),
  br(), cln('Clanarina'),
  pg('Visinu i nacin placanja clanarine utvrdjuje Skupstina godisnje.', { j: true }),
  br(),
  h1('VI. RJESAVANJE SPOROVA'),
  cln('Mirno rjesavanje sporova'),
  pg('Sporovi se rjesavaju mirnim putem. Ako nije moguce, nadlezan je sud prema sjedistu udruge.', { j: true }),
  br(),
  h1('VII. PRESTANAK UDRUGE'),
  cln('Prestanak rada'),
  pg('Udruga prestaje odlukom Skupstine dvotreci%nskom veinom, sudskim rjesenjem ili spajanjem. Imovina se prenosi na udrugu s istovrsnim ciljevima.', { j: true }),
  br(),
  h1('VIII. ZAVRSNE ODREDBE'),
  cln('Stupanje na snagu'),
  pg(`Statut je donesen na Osnivackoj skupstini udruge ${UDRUGA} dana ${DATUM} u Vladislavcima i stupa na snagu danom upisa u Registar udruga.`, { j: true }),
  br(), br(),
  pg(`U Vladislavcima, ${DATUM_K}`, { c: true }), br(),
  pg('Predsjednik osnivacke skupstine:', { c: true }),
  new Paragraph({ spacing: { before: 580, after: 60 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: '___________________________', font: 'Arial', size: 22 })] }),
  pg(P1.ime, { c: true, bold: true }),
]}]});

// ZAPISNIK
const zapisnik = new Document({ numbering: num, styles: sty, sections: [{ properties: pgProp, children: [
  ...hdr('ZAPISNIK', 'Osnivacke skupstine udruge'),
  br(),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: 'Datum: ', bold: true, font: 'Arial', size: 22 }), new TextRun({ text: `${DATUM} u Vladislavcima`, font: 'Arial', size: 22 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: 'Mjesto: ', bold: true, font: 'Arial', size: 22 }), new TextRun({ text: ADRESA, font: 'Arial', size: 22 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: 'Prisutni osnivaci: ', bold: true, font: 'Arial', size: 22 }), new TextRun({ text: `${P1.ime}, ${P2.ime}, ${P3.ime}`, font: 'Arial', size: 22 })] }),
  new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text: 'Predsjedava: ', bold: true, font: 'Arial', size: 22 }), new TextRun({ text: P1.ime, font: 'Arial', size: 22 })] }),
  new Paragraph({ spacing: { after: 300 }, children: [new TextRun({ text: 'Zapisnicar: ', bold: true, font: 'Arial', size: 22 }), new TextRun({ text: P3.ime, font: 'Arial', size: 22 })] }),
  new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 4, color: '1A3A6B' } }, spacing: { before: 100, after: 280 }, children: [] }),
  h2('DNEVNI RED'),
  nump('Otvaranje skupstine i utvrdivanje kvoruma'),
  nump(`Donosenje odluke o osnivanju udruge "${UDRUGA}"`),
  nump('Utvrdivanje sjedista udruge'),
  nump('Donosenje Statuta udruge'),
  nump('Izbor predsjednika udruge'),
  nump('Izbor tajnika udruge'),
  nump('Ostalo'),
  br(), h2('TIJEK SKUPSTINE'), br(),
  pg('Ad 1. Otvaranje skupstine', { bold: true }),
  pg(`${P1.ime} otvorio je skupstinu i utvrdio da su prisutni svi osnivaci — skupstina je sposobna za rad i pravovaljano donosenje odluka.`, { j: true }),
  br(),
  pg('Ad 2. Odluka o osnivanju udruge', { bold: true }),
  pg(`Prisutni osnivaci jednoglasno su donijeli odluku o osnivanju Udruge "${UDRUGA}" sa sjeDistem u Vladislavcima.`, { j: true }),
  decisBox(`ODLUKA: Osniva se udruga "${UDRUGA}", sjediste: ${ADRESA}.`),
  pg('Glasanje: ZA — 3, PROTIV — 0, SUZDRZANI — 0', { c: true, i: true }), br(),
  pg('Ad 3. Sjediste udruge', { bold: true }),
  pg(`Sjediste udruge: ${ADRESA}.`, { j: true }), br(),
  pg('Ad 4. Donosenje Statuta', { bold: true }),
  pg(`Skupstina je jednoglasno usvojila Statut udruge "${UDRUGA}" u cijelosti.`, { j: true }),
  decisBox(`ODLUKA: Statut udruge "${UDRUGA}" usvojen je u cijelosti.`),
  pg('Glasanje: ZA — 3, PROTIV — 0, SUZDRZANI — 0', { c: true, i: true }), br(),
  pg('Ad 5. Izbor predsjednika', { bold: true }),
  pg(`Za predsjednika udruge jednoglasno je izabran ${P1.ime}.`, { j: true }),
  decisBox(`ODLUKA: Za predsjednika udruge izabran je ${P1.ime}.`),
  pg('Glasanje: ZA — 3, PROTIV — 0, SUZDRZANI — 0', { c: true, i: true }), br(),
  pg('Ad 6. Izbor tajnika', { bold: true }),
  pg(`Za tajnika udruge jednoglasno je izabran ${P2.ime}.`, { j: true }),
  decisBox(`ODLUKA: Za tajnika udruge izabran je ${P2.ime}.`),
  pg('Glasanje: ZA — 3, PROTIV — 0, SUZDRZANI — 0', { c: true, i: true }), br(),
  pg('Ad 7. Ostalo', { bold: true }),
  pg('Nije bilo dodatnih tocaka. Predsjedavajuci je zahvalio prisutnim osnivacima i zakljucio skupstinu.', { j: true }), br(),
  new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 4, color: '1A3A6B' } }, spacing: { before: 200, after: 200 }, children: [] }),
  pg(`Skupstina zakljucena u Vladislavcima, ${DATUM_K}`, { c: true }), br(),
  new Table({ width: { size: 9026, type: WidthType.DXA }, columnWidths: [4513, 4513], rows: [new TableRow({ children: [
    new TableCell({ borders: nob, width: { size: 4513, type: WidthType.DXA }, margins: mc, children: [
      pg('Predsjedavajuci:', { bold: true }),
      new Paragraph({ spacing: { before: 560 }, children: [new TextRun({ text: '___________________________', font: 'Arial', size: 22 })] }),
      pg(P1.ime),
    ]}),
    new TableCell({ borders: nob, width: { size: 4513, type: WidthType.DXA }, margins: mc, children: [
      pg('Zapisnicar:', { bold: true }),
      new Paragraph({ spacing: { before: 560 }, children: [new TextRun({ text: '___________________________', font: 'Arial', size: 22 })] }),
      pg(P3.ime),
    ]}),
  ]}]}),
]}]});

// POPIS OSNIVACA
const widths = [400, 1900, 1600, 1400, 3526, 1800];
const hRowP = new TableRow({ tableHeader: true, children: ['R.br.','Ime i prezime','OIB','Datum rodenja','Adresa prebivalista','Funkcija'].map((t, i) =>
  new TableCell({ borders: brd, width: { size: widths[i], type: WidthType.DXA }, shading: { fill: '1A3A6B', type: ShadingType.CLEAR }, margins: mc, children: [new Paragraph({ children: [new TextRun({ text: t, bold: true, font: 'Arial', size: 19, color: 'FFFFFF' })] })] }))
});
const dRowP = (n, per, fn, shade) => new TableRow({ children: [n, per.ime, per.oib, per.dob, per.adresa, fn].map((t, i) =>
  new TableCell({ borders: brd, width: { size: widths[i], type: WidthType.DXA }, shading: { fill: shade, type: ShadingType.CLEAR }, margins: mc, children: [new Paragraph({ children: [new TextRun({ text: t, bold: i===1, font: 'Arial', size: 21 })] })] }))
});

const popis = new Document({ numbering: num, styles: sty, sections: [{ properties: { page: { size: { width: 16838, height: 11906 }, margin: { top: 1200, right: 1200, bottom: 1200, left: 1200 } } }, children: [
  ...hdr('POPIS OSNIVACA', `Udruge "${UDRUGA}"`),
  pg(`Na Osnivackoj skupstini dana ${DATUM} u ${ADRESA}, osnivaci su:`, { j: true }), br(),
  new Table({ width: { size: 10626, type: WidthType.DXA }, columnWidths: widths, rows: [
    hRowP,
    dRowP('1.', P1, 'Predsjednik', 'FFFFFF'),
    dRowP('2.', P2, 'Tajnik', 'F5F5F5'),
    dRowP('3.', P3, 'Zapisnicar', 'FFFFFF'),
  ]}),
  br(),
  pg('Napomena: Za Kruljac Ivicu adresa ce biti potvrdjbena prilaganjem osobne iskaznice.', { i: true }),
  br(), br(),
  pg(`U Vladislavcima, ${DATUM_K}`, { c: true }), br(),
  new Table({ width: { size: 9026, type: WidthType.DXA }, columnWidths: [3000, 3000, 3026], rows: [new TableRow({ children: [
    [P1.ime, P2.ime, P3.ime].map((n, i) =>
      new TableCell({ borders: nob, width: { size: [3000,3000,3026][i], type: WidthType.DXA }, margins: mc, children: [
        pg(n, { bold: true }),
        new Paragraph({ spacing: { before: 560 }, children: [new TextRun({ text: '___________________________', font: 'Arial', size: 22 })] }),
      ]})
    )
  ]}]}),
]}]});

// ZAHTJEV RU-1
const iRow = (lbl, val) => new TableRow({ children: [
  new TableCell({ borders: brd, width: { size: 3200, type: WidthType.DXA }, shading: { fill: 'E8EEF4', type: ShadingType.CLEAR }, margins: mc, children: [new Paragraph({ children: [new TextRun({ text: lbl, bold: true, font: 'Arial', size: 20 })] })] }),
  new TableCell({ borders: brd, width: { size: 6826, type: WidthType.DXA }, shading: { fill: 'FFFFFF', type: ShadingType.CLEAR }, margins: mc, children: [new Paragraph({ children: [new TextRun({ text: val, font: 'Arial', size: 22 })] })] }),
]});

const zahtjev = new Document({ numbering: num, styles: sty, sections: [{ properties: pgProp, children: [
  new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { after: 60 }, children: [new TextRun({ text: 'Obrazac RU-1 — Zakon o udrugama (NN 74/14, 70/17, 98/19)', font: 'Arial', size: 18, italics: true, color: '777777' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: 'REPUBLIKA HRVATSKA — Ministarstvo unutarnjih poslova', bold: true, font: 'Arial', size: 22, color: '555555' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: 'Policijska uprava Osjecko-baranjska', font: 'Arial', size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [new TextRun({ text: 'Odjel za opcu upravu — Registar udruga', font: 'Arial', size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: 'ZAHTJEV ZA UPIS UDRUGE U REGISTAR UDRUGA', bold: true, size: 28, font: 'Arial', color: '1A3A6B' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 360 }, children: [new TextRun({ text: 'temeljem cl. 9. Zakona o udrugama', font: 'Arial', size: 22, italics: true })] }),
  h2('I. PODACI O UDRUZI'),
  new Table({ width: { size: 10026, type: WidthType.DXA }, columnWidths: [3200, 6826], rows: [
    iRow('Naziv udruge:', `UDRUGA ${UDRUGA}`),
    iRow('Skraceni naziv:', UDRUGA),
    iRow('Sjediste:', ADRESA),
    iRow('Podrucje djelovanja:', 'Republika Hrvatska i medunarodna razina'),
    iRow('Datum osnivanja:', DATUM_K),
    iRow('Ciljevi:', 'Promicanje prava na gotovinska placanja, financijska privatnost, Open Source'),
  ]}),
  br(), h2('II. ZASTUPNIK — PREDSJEDNIK'),
  new Table({ width: { size: 10026, type: WidthType.DXA }, columnWidths: [3200, 6826], rows: [
    iRow('Ime i prezime:', P1.ime), iRow('OIB:', P1.oib), iRow('Datum rodenja:', P1.dob),
    iRow('Adresa:', P1.adresa), iRow('Funkcija:', 'Predsjednik udruge — zakonski zastupnik'),
  ]}),
  br(), h2('III. TAJNIK'),
  new Table({ width: { size: 10026, type: WidthType.DXA }, columnWidths: [3200, 6826], rows: [
    iRow('Ime i prezime:', P2.ime), iRow('OIB:', P2.oib), iRow('Adresa:', P2.adresa),
  ]}),
  br(), h2('IV. PRILOZENA DOKUMENTACIJA'),
  bul('Statut udruge (2 primjerka, potpisana od predsjedavajuceg osnivacke skupstine)'),
  bul('Zapisnik osnivacke skupstine (2 primjerka, potpisana)'),
  bul('Popis osnivaca s OIB podacima i potpisima'),
  bul('Preslike osobnih iskaznica svih osnivaca'),
  br(),
  new Paragraph({ border: { top: { style: BorderStyle.SINGLE, size: 4, color: '1A3A6B' } }, spacing: { before: 100, after: 280 }, children: [] }),
  pg(`U Vladislavcima, ${DATUM_K}`), br(),
  pg('Podnositelj zahtjeva — predsjednik udruge:', { bold: true }),
  new Paragraph({ spacing: { before: 580, after: 60 }, children: [new TextRun({ text: '___________________________', font: 'Arial', size: 22 })] }),
  pg(P1.ime, { bold: true }), pg(`OIB: ${P1.oib}`),
]}]});

// GENERATE
const OUT = '/var/www/fina-connect/static/udruga_no_limit/';
await Packer.toBuffer(statut).then(b => fs.writeFileSync(OUT+'NO_LIMIT_Statut.docx', b));
await Packer.toBuffer(zapisnik).then(b => fs.writeFileSync(OUT+'NO_LIMIT_Zapisnik_osnivacke_skupstine.docx', b));
await Packer.toBuffer(popis).then(b => fs.writeFileSync(OUT+'NO_LIMIT_Popis_osnivaca.docx', b));
await Packer.toBuffer(zahtjev).then(b => fs.writeFileSync(OUT+'NO_LIMIT_Zahtjev_RU1.docx', b));
console.log('DOCX OK');
