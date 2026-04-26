# SONNET_TASK: ARHITEKTURA_R3 — Kvantni bunker faza 2-4
## Agent: Sonnet (arhitektura) | Prioritet: VISOK | Rok: 2-4 sesije

---

## KONTEKST

Nakon što CC Code završi CC_TASK_QUANTUM_AKTIVACIJA.md (liboqs, argon2, blake3, nginx),
Sonnet preuzima arhitekturalnu razinu koja zahtijeva dizajn odluke.

---

## ZADATAK A — RFC 3161 Timestamping za ChainBlock i Genesis

### Cilj
Svaki POE token (Genesis Block i svaki ChainBlock entry) mora imati RFC 3161
timestamp od akreditiranog TSA. Ovo je razlika između "naš sustav kaže" i
"neovisni akreditirani autoritet potvrđuje" — sud prihvaća RFC 3161 bez vještaka.

### Implementacija

```python
# Novi model: chain/tsa_stamp.py

class TSAStamp(models.Model):
    """RFC 3161 Trusted Timestamp za ChainBlock POE."""
    chain_entry = models.OneToOneField('ChainEntry', on_delete=models.PROTECT,
                                        related_name='tsa_stamp')
    tsa_provider = models.CharField(max_length=100)  # 'FreeTSA', 'DigiCert', 'FINA'
    hash_algorithm = models.CharField(max_length=20, default='SHA-512')
    message_imprint = models.CharField(max_length=128)  # hex hash koji je timestampan
    tsa_token_b64 = models.TextField()  # RFC 3161 token (DER encoded, base64)
    serial_number = models.BigIntegerField()
    gen_time = models.DateTimeField()  # TSA potvrđeno vrijeme
    verified_at = models.DateTimeField(null=True)
    is_valid = models.BooleanField(default=True)

    def verify(self) -> bool:
        """Verificiraj TSA token kriptografski."""
        # Koristiti rfc3161ng ili python-rfc3161
        pass
```

Koristiti FreeTSA (besplatno, RFC 3161 kompatibilno):
```bash
openssl ts -query -data file.pdf -no_nonce -sha512 -out request.tsq
curl -H "Content-Type: application/timestamp-query" \
     --data-binary @request.tsq https://freetsa.org/tsr > response.tsr
openssl ts -verify -in response.tsr -queryfile request.tsq -CAfile cacert.pem
```

---

## ZADATAK B — HSM integracija za TAJNA ključeve

### Cilj
TAJNA_KLJUČ danas živi enkriptiran u fajl sistemu. Rizik: root pristup = sve.
HSM: privatni ključevi nikad ne napuštaju hardver. Softver samo šalje podatke,
HSM vraća encrypted/signed output.

### Opcije (redom po cijeni/zahtjevnosti)

1. **Nitrokey HSM 2** (~60 EUR) — USB HSM, PKCS#11 interface, Python: python-pkcs11
2. **AWS CloudHSM** (~1.60 USD/h) — cloud HSM, preskupo za sada
3. **SoftHSM2** (besplatno) — software HSM za testiranje, nema fizičku zaštitu

### Plan implementacije

**Faza 1 (odmah):** SoftHSM2 za testiranje arhitekture
```bash
apt install softhsm2
pip install python-pkcs11 --break-system-packages
```

**Faza 2 (kad prihodi porastu):** Nitrokey HSM 2 fizički uređaj

```python
# core/hsm_provider.py
import pkcs11

class HSMKeyStore:
    """PKCS#11 interface za HSM ili SoftHSM."""

    def sign(self, data: bytes, key_label: str) -> bytes:
        """Potpiši podatke — privatni ključ nikad ne izlazi iz HSM-a."""
        pass

    def decrypt(self, ciphertext: bytes, key_label: str) -> bytes:
        """Dešifriraj — ključ ostaje u HSM-u."""
        pass
```

---

## ZADATAK C — Geografski distribuirani ChainBlock

### Cilj
chain.json trenutno živi samo na jednom serveru (37.27.248.86).
Razina 4 = 3 neovisne lokacije, sve s kriptografski verificiranim chain.json.

### Arhitektura

```
Primarni  → 37.27.248.86 (Hetzner Frankfurt) — master
Mirror 1  → IPFS (pin via Pinata ili nft.storage) — decentralizirani
Mirror 2  → BunkerSeal čvor (budući drugi server) — redundancija
```

### Implementacija

```python
# chain/mirror_sync.py — Celery task

@app.task(name="chain.sync_mirrors", queue="default")
def sync_chain_mirrors():
    """
    Svakih 15 minuta sinkronizira chain.json na sve mirrore.
    Ako se mirrori ne slažu s masterom → SentinelAlert.
    """
    import ipfshttpclient

    chain_data = open("/var/www/fina-connect/static/udruga_no_limit/genesis/NOLIMIT-GENESIS-0001.chain.json").read()
    chain_hash = hashlib.sha3_256(chain_data.encode()).hexdigest()

    # IPFS pin
    client = ipfshttpclient.connect()
    result = client.add_str(chain_data)
    ipfs_cid = result

    # Log u DB
    ChainMirrorSync.objects.create(
        master_hash=chain_hash,
        ipfs_cid=ipfs_cid,
        synced_at=timezone.now(),
    )
```

---

## ZADATAK D — Novi Zakon 25 za FENIX_ZAKON.md

Nakon implementacije svih R1-R3 koraka, dodati u FENIX_ZAKON.md:

```markdown
## ZAKON 25 — POST-KVANTNA KRIPTOGRAFIJA JE ZAKON, NE OPCIJA

Status od [datum]: liboqs-python AKTIVAN u produkciji.

| Algoritam | Svrha | Status |
|-----------|-------|--------|
| Kyber-768 | KEM — razmjena ključeva | ✅ AKTIVAN |
| Kyber-1024 | KEM — dokumenti R4+ | ✅ AKTIVAN |
| Dilithium3 | Potpisi — AuditLog | ✅ AKTIVAN |
| BLAKE3 | Hash — ChainBlock | ✅ AKTIVAN |
| Argon2id | KDF — lozinke/VIVUS | ✅ AKTIVAN |
| RFC 3161 | Timestamp — POE | 🔄 U TOKU |
| HSM | Ključ storage | 🔄 PLANIRAN |

ZABRANA:
- MD5, SHA-1 — ne koristiti nigdje
- PBKDF2 — samo za backward compat s postojećim .dok fajlovima
- RSA < 4096 — ne generirati nove RSA ključeve
- AES-128 — koristiti isključivo AES-256

Svaki novi kriptografski kod mora biti pregledan ovim zakonom.
```

---

## ZADATAK E — Onboarding Marija i Ljubica (paralelno)

Ovo nije sigurnosni zadatak ali je KRITIČAN za prihod.

Pročitati CC_TASK_KORAK10_ONBOARDING.md i:
1. Provjeriti što je implementirano, što blokira
2. Napisati konkretan 3-koračni plan za Marijin workflow
3. Definirati koji bugovi blokiran pravi rad (ne test rad)

---

## REDOSLIJED SESIJA

```
Sesija 1 (CC Code):  CC_TASK_QUANTUM_AKTIVACIJA.md — instalacije + nginx
Sesija 2 (Sonnet):   Zadatak A (RFC 3161) + Zadatak D (Zakon 25)
Sesija 3 (CC Code):  Zadatak B faza 1 (SoftHSM2) + Zadatak C (IPFS mirror)
Sesija 4 (Sonnet):   Zadatak E (Onboarding) + audit svih promjena
```
