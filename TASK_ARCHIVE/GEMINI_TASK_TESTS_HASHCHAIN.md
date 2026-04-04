# GEMINI_TASK_TESTS_HASHCHAIN

## Cilj
Napisati Django testove za pos/hashchain.py i PLG Virus implementaciju (commit 73a0701, 81ee45a).

## Fajl za pisanje
`pos/tests_hashchain.py` — NOVI fajl

## Što testirati

### Hash Chain — core logika

#### Test 1: append_receipt() — prva karika (genesis)
```
- Kreiraj Company, Terminal, Session, POSReceipt (sa stavkama)
- Pozovi append_receipt(receipt)
- Assert: ChainLink.objects.count() == 1
- Assert: link.sequence == 1
- Assert: link.prev_hash == '0' * 64
- Assert: link.chain_hash nije prazan
- Assert: link.receipt == receipt
```

#### Test 2: append_receipt() — lanac 3 karike
```
- Kreiraj 3 receipta i pozovi append_receipt za svaki
- Assert: link2.prev_hash == link1.chain_hash
- Assert: link3.prev_hash == link2.chain_hash
- Assert: sva 3 imaju unique chain_hash
```

#### Test 3: verify_chain() — integritet OK
```
- 5 receipta u lancu
- verify_chain(company) → (True, None, 5)
```

#### Test 4: verify_chain() — tampered receipt (falsifikat)
```
- 3 recepta, lanac OK
- Direktno u DB: ChainLink.objects.filter(sequence=2).update(payload_hash='a'*64)
- verify_chain(company) → (False, 2, 3)
- Assert: break_point == 2
```

#### Test 5: verify_single() — receipt nepromijenjen
```
- append_receipt(receipt)
- verify_single(receipt) → True
```

#### Test 6: verify_single() — receipt modificiran
```
- append_receipt(receipt)
- Receipt.objects.filter(pk=receipt.pk).update(total=Decimal('9999.99'))
- verify_single(receipt) → False
```

#### Test 7: verify_single() — receipt nije u lancu
```
- Kreiraj receipt ALI ne pozivaj append_receipt
- verify_single(receipt) → None
```

#### Test 8: daily_anchor_hash() — vraća string
```
- 3 recepta u lancu za danas
- anchor = daily_anchor_hash(company)
- Assert: isinstance(anchor, str)
- Assert: len(anchor) == 64  # SHA256
```

#### Test 9: daily_anchor_hash() — prazan dan
```
- Nema chain linkova za danas
- daily_anchor_hash(company) → None
```

#### Test 10: _sha256 determinizam
```
- Isti input uvijek daje isti hash
- _sha256('test') == _sha256('test')
- _sha256('test') != _sha256('Test')
```

### PLG Virus — chain_link_safe property

#### Test 11: chain_link_safe — receipt u lancu
```
- append_receipt(receipt)
- receipt.chain_link_safe → vraća ChainLink objekt (ne crasha)
```

#### Test 12: chain_link_safe — receipt nije u lancu
```
- POSReceipt bez chain_link
- receipt.chain_link_safe → None (ne baca DoesNotExist)
```

### Checkout integracija

#### Test 13: checkout dodaje u lanac
```
- Pozovi CheckoutService._finalize_receipt() ili ekvivalent
- Assert: ChainLink kreirano za receipt
- HINT: provjeri pos/services/checkout.py kako se zove append_receipt
```

## Model setup helpers

```python
# Čitaj STVARNA polja iz pos/models.py PRIJE pisanja!
# Posebno: POSReceipt, POSReceiptItem, POSSession, POSTerminal
# NE pretpostavljaj: total vs grand_total, terminal vs pos_terminal, itd.

def _make_company():
    from companies.models import Company
    import uuid
    return Company.objects.create(name='Test Co ' + str(uuid.uuid4())[:8], oib='12345678901')

def _make_receipt(company):
    # CC Code: pročitaj pos/models.py PRVO!
    # Napravi minimalni receipt sa svim required poljima
    pass
```

## Pokretanje

```bash
cd /var/www/fina-connect
source venv/bin/activate
python manage.py test pos.tests_hashchain --verbosity=2
```

## KRITIČNO za CC Code i Gemini
1. **OBAVEZNO** pročitaj `pos/models.py` i `pos/hashchain.py` PRIJE pisanja testa
2. Provjeri kako checkout.py zove append_receipt — direktno ili signal?
3. Za `_receipt_payload()` — koristi `receipt.items.order_by('pk').all()` — provjeri related_name
4. `TransactionTestCase` za testove koji testiraju DB integritet
5. NE koristi `TestCase` za Zamku 3 i concurrent testove
