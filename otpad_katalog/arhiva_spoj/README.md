# Spajanje slika dijelova s poslovnom arhivom (ARHIVA 2030)

**Stanje:** adapter i ekran su gotovi i testirani na LAŽNOJ arhivi (ugovor pročitan iz koda na EU). Na stvarnu arhivu
se NIJE spajalo: za to treba zakrpa na produkciji (A4) i servisna sesija koju može dati samo Ivan.

## Što je pročitano (izvor istine, EU)
- `api/arhiva_core.py` `POST /api/v1/arhiva-core/upload-datoteka` (multipart `datoteka`, `app_id`; sesija GenesisLogin; creator i
  tenant se izvode iz sesije, nikad iz zahtjeva). `GET /{weise3_id}/original` vraća sirove bajtove.
- `services/arhiva_core/ulaz.py` `primi_dokument`: ključ = hash sadržaja + kreatora (isti sadržaj = isti id), readback prije retka.
- `services/dokarh_resolver.py` `put`: sprema zapečaćeni dokument na lokalni disk i na SVE dodane Bršljan peer čvorove (replikacija
  dokumenata; ovo NIJE Krunica). Binarni sadržaj (slike) ostaje netaknut.
- `services/arhiva_core/obrada.py`: **svaki upload pokreće obradu u pozadini: OCR, odvajanje podloge i DVA AI poziva** (vizualno i
  semantičko, preko token routera). Za fotografije dijelova to je trošak bez koristi, a limit troška je 0 dok nije upisan u lanac.

**Ažurirano 2026-10-13:** korak 2 je IZVEDEN na EU (vidi FENIX_SOBA.md, odjeljak "DA primijeni-zakrpu-bez-ai"), ali preko `write_file` cijele datoteke, bez INTENT/RAČUN atoma. Korak 3 (mjerenje sa servisnom sesijom) tek slijedi; do tada se `ARHIVA_BEZ_AI_POTVRDENO=1` ne uključuje.

## Zašto zakrpa
Bez nje bi svaka fotografija dijela (tisuće) pokrenula plaćenu AI obradu i zatrpala knjigovođin popis računa. Zakrpa
(`primijeni_zakrpu.py`) preskače obradu SAMO za app_id `kelava-dijelovi`; ručni `/obradi` ostaje. Adapter se ne da uključiti
bez `ARHIVA_BEZ_AI_POTVRDENO=1`, a ekran se bez toga ne pokreće (test A1).

## Koraci (redom; ✋ = treba Ivanov `DA`)
1. ✋ Kelava tenant u GenesisLoginu i servisna sesija (token) za ekran. Token ide u okolinu ekrana, nikad u repo ni u razgovor.
2. ✋ `DA primijeni-zakrpu-bez-ai eu-genesis`: INTENT atom → `python3 primijeni_zakrpu.py /var/www/genesis/api/arhiva_core.py --suho`
   (mora ispisati dva različita sha256 i "SUHO") → bez `--suho` → restart `genesis` → RAČUN atom (hash prije/poslije) + rollback
   koji ispiše skripta. Testirano samo na fixturi (Z1), ne na pravoj datoteci.
3. Mjerenje na stvarnoj arhivi (A3, tek nakon 2.): 3 slike kroz ekran → `ai_status` ostaje `pending`, u `get_logs genesis` nema
   AI poziva, `GET /original` bajt-identičan. Ako se AI ipak pokrene: odmah vratiti zakrpu (rollback) i prijaviti.
4. Na ekranu: `ARHIVA_URL=https://genesis.limit-connect.com ARHIVA_TOKEN=… ARHIVA_BEZ_AI_POTVRDENO=1` (uz `OTPAD_SLIKE`, ako
   ostaju stare lokalne slike; one ostaju čitljive).

## Što još nije riješeno (ne blokira korake gore)
- **Webshop:** `/original` traži sesiju. Javne slike za oglas treba posluživati ili javnom adresom arhive (`/v/{weise3_id}` je
  javna za provjeru, ne za sliku) ili preko webshopa sa servisnom sesijom. Izlazni red već nosi `OGLAS` sa popisom javnih slika.
- **Rok čuvanja:** arhiva svakom dokumentu daje 11 godina čuvanja (`retain_until`), brisanje ide kroz Trojstvo 2/3 (dva glasa +
  24 h hlađenja). Za fotografije dijelova to znači da se ne brišu lako. Treba odluka je li to željeno.
- **Podloga za webshop:** pipeline zna odvojiti podlogu i dati transparentni sloj (korisno za oglase), ali je to dio iste obrade koja
  zove AI. Besplatni dio (samo lokalno odvajanje) treba zaseban način rada u `obrada.py` (A4 izmjena, nije pisana).
- Trošak: dok limit nije upisan u lanac, nijedan AI poziv nad slikama dijelova.

## Dodatni nalazi (2026-10-13, čitanje `obrada.py`, `strazar.py`, `strazar_ophodnja.py`)
- **Krunica:** `obradi_dokument` na kraju zove `upisi_kao_dokarh`, koji upisuje bajtove dokumenta kao DokArh blok u Krunicu (ChainBlock, vječan,
  replicira se). Zakrpa preskače cijelu obradu za `kelava-dijelovi`, pa se **sadržaj fotografije dijela ne upisuje u Krunicu**; ostaje u Sloju 1
  (resolver: lokalni disk + Bršljan peerovi) i u retku arhive. Ako ikada želiš da javne slike ipak idu u Krunicu, to je zasebna odluka.
- **Servisna sesija MORA imati aktivni tenant:** bez njega stražar svakoj fotografiji upisuje alarm `T1_BEZ_KOMITENTA` i `strazar/zdravlje` postaje ALARM.
- **Prozor stražara:** ophodnja svakih 10 min uzima 200 najnovijih nezapečaćenih dokumenata iz 14 dana. Masovni upload fotografija izgurao bi stvarne
  račune iz prozora. Rješenje je `primijeni_zakrpu_strazar.py` (isključuje `kelava-dijelovi`, NULL-sigurno; testirano na fixturi i stvarnim SQL-om na sqlite).
  **NIJE primijenjeno** (A4, traži DA: `DA primijeni-zakrpu-strazar eu-genesis`). Primijeniti prije prvog većeg uploada.
- Ophodnja NE zove obradu (provjereno), pa zakrpa nije zaobiđena tim putem. Drugi pozivatelji `obradi_dokument` nisu pretraženi (MAX grep je nepouzdan).
