# Boxgram — Meta App Review Plan (Faza 2)

## Sažetak

Boxgram je aplikacija za upravljanje životima kućnih ljubimaca s mogućnošću dijeljenja na društvenim mrežama (pet social network). Trenutna Faza 1 omogućava import objava sa Facebooka, TikToka i YouTubea, a Faza 2 će omogućiti dijeljenje direktno na Meta platforme (Facebook, Instagram).

## Opseg Faze 2 — Meta Integration

### 2.1 Facebook/Instagram Login Integration
- Korisnici se mogu prijaviti s Meta korisničkim računima
- Permisije:
  - `email` — osnovne informacije
  - `public_profile` — javni profil korisnika
  - `user_friends` — lista prijatelja (opciono, za pronalaženje prijatelja)

### 2.2 Publish to Facebook
- Korisnik bira koju objavu (LifeEvent) želi dijeliti
- Odabire ciljnu stranicu ili profil
- Prilagođava naslov/tekst prije objavljivanja
- API: Facebook Graph API `/me/feed` endpoint
- Permisije: `pages_manage_posts`, `pages_read_engagement`

### 2.3 Publish to Instagram Stories / Feed
- Mogućnost objavljivanja slike na Instagram profil
- Permisije: `instagram_basic`, `instagram_content_publishing`
- Limitirajuće: Samo slika (ne video) zbog Instagram ograničenja

### 2.4 Scheduled Posts
- Korisnik bira datum/vrijeme objavljivanja
- Zadatak u Celery Queue: `boxgram.tasks.scheduled_post_to_facebook`
- Pohrana u `ScheduledPost` model

## Modeli (Faza 2)

```python
class MetaIntegration(models.Model):
    user = ForeignKey(User)
    platform = CharField(choices=['facebook', 'instagram'])
    access_token = EncryptedCharField()
    refresh_token = EncryptedCharField(null=True)
    token_expires_at = DateTimeField()
    page_id = CharField(null=True)
    created_at = DateTimeField(auto_now_add=True)

class ScheduledPost(models.Model):
    user = ForeignKey(User)
    life_event = ForeignKey(LifeEvent)
    platform = CharField(choices=['facebook', 'instagram'])
    scheduled_at = DateTimeField()
    status = CharField(choices=['scheduled', 'posted', 'failed'])
    external_post_id = CharField(null=True, unique=True)
    error_message = TextField(blank=True)
```

## API Endpoints (Faza 2)

### Prijava na Meta

```
POST /api/boxgram/meta/authorize/
Body: { redirect_uri, scope }
Response: { auth_url }
```

### Callback nakon Meta prijave

```
GET /api/boxgram/meta/callback/?code=..&state=..
Response: Redirect na dashboard, cookie sa signed in statusom
```

### Listaj dostupne Facebook stranice

```
GET /api/boxgram/meta/pages/
Response: { pages: [ { id, name, access_token } ] }
```

### Objavi na Facebook

```
POST /api/boxgram/meta/publish/
Body: {
    life_event_id,
    platform: 'facebook',
    page_id,
    title,
    scheduled_at (optional)
}
Response: { post_id, url, status }
```

## Meta App Review Checklist

### 1. Osnovne informacije
- [ ] App name: "Boxgram Pet Stories"
- [ ] App category: Lifestyle
- [ ] App description: "Share your pet's life moments on social media"
- [ ] Opis korištenja API-ja: Import i objavljivanje objava vezanih uz ljubimce

### 2. Permisije koje trebamo
- [ ] `email` — Prikaz email adrese (Tier 1 — Auto odobreno)
- [ ] `public_profile` — Javni profil (Tier 1 — Auto odobreno)
- [ ] `pages_manage_posts` — Objave na stranicama (Tier 3 — Zahtijeva review)
- [ ] `pages_read_engagement` — Čitanje statusa objava (Tier 2 — Zahtijeva review)
- [ ] `instagram_basic` — Instagram profil (Tier 2 — Zahtijeva review)
- [ ] `instagram_content_publishing` — Objavljivanje na Instagram (Tier 3 — Zahtijeva review)

### 3. Dokumentacija za Meta
- [ ] Privacy Policy ažurirana za Meta login
- [ ] Terms of Service sa informacijom o dijeljenju na Meta platformama
- [ ] Podatke čuvaš maksimalno 24h osim access tokena (lifetime, refreshable)

### 4. Sigurnosne provjere
- [ ] HTTPS za sve endpoints
- [ ] Tokenе čuvaj u encrypted polju (EncryptedCharField)
- [ ] Nemoj stovaritit tokene u logovanju
- [ ] Validiraj sve inpute prije Meta API poziva

### 5. User Experience
- [ ] Jasna poruka o tome što aplikacija radi s Meta podacima
- [ ] Jednostavno odbijanje / revokacija pristupa
- [ ] Logout iz aplikacije = revoke tokena na Meta-i

### 6. Testing
- [ ] Test sa development app-om
- [ ] Test sve tri permisije grupe
- [ ] Test token refresh logic
- [ ] Test error handling (invalid token, expired token)

## Timeline

- **Tjedan 1-2**: Komp design + UI za Meta login
- **Tjedan 2-3**: Backend implementacija + testing
- **Tjedan 3-4**: Meta App Review submission
- **Tjedan 4-6**: Čekanje na approval (obično 1-2 tjedna)
- **Tjedan 6-7**: Production release

## Resursi

- [Meta Login Documentation](https://developers.facebook.com/docs/facebook-login/web)
- [Graph API Pages](https://developers.facebook.com/docs/graph-api/reference/page)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-api)
- [App Review Best Practices](https://developers.facebook.com/docs/app-review/guidelines)

---

**Zadnje ažurirano**: 2026-04-05
