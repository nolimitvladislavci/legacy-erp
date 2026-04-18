# CC_TASK — GAMES BUGFIX (Antonio tester session)
> Datum: 2026-04-18 | Tester: Antonio Brtan | Zapisao: Sonnet

---

## BUG 1 — MEMORIJA NE RADI NA iPHONE

**Uzrok:** iOS Safari ne šalje `click` event na div elemente koji nisu nativno klikabilni.
**Fix:** Dodati `cursor: pointer` + `touchstart` event listener uz `click`.

Naći u templates/memio_world/memory_game.html:
```javascript
// STARO
card.addEventListener('click', flipCard);

// NOVO — iOS kompatibilno
card.addEventListener('click', flipCard);
card.addEventListener('touchstart', function(e) {
  e.preventDefault(); // Sprječava double-fire
  flipCard.call(this, e);
}, {passive: false});
```

CSS fix:
```css
.memory-card {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent; /* Makni iOS plavi flash */
  touch-action: manipulation; /* Sprječava zoom na double-tap */
}
```

---

## BUG 2 — KVIZ: REZULTAT 0 KAD SVE TOČNO

**Uzrok:** Gotovo sigurno tip usporedbe. Pregledati score logiku.

Naći u kviz template, tražiti:
```javascript
// PROBLEM — vjerojatni kod:
if (userAnswer == correctAnswer) score++;

// Provjeri je li correctAnswer string ili int:
console.log(typeof correctAnswer, typeof userAnswer);

// FIX — eksplicitna string usporedba:
if (String(userAnswer).trim() === String(correctAnswer).trim()) score++;
```

Ili: score se resetira nakon prikaza. Tražiti:
```javascript
// Problem: score = 0 na krivom mjestu
// score = 0; // Ova linija mora biti SAMO na početku kviza, ne na kraju
```

---

## BUG 3 — MUDROSTI: POGREŠNA KATEGORIJA (avion, balon kao životinje)

**Uzrok:** Seed podaci — pitanja nisu filtrirana po kategoriji ili je kategorija kriva.

```bash
# Provjeri u Django shellu:
cd /var/www/fina-connect
venv/bin/python manage.py shell -c "
from memio_world.quiz_models import QuizQuestion
wrong = QuizQuestion.objects.filter(category='animals').filter(
    answer_a__icontains='avion'
) | QuizQuestion.objects.filter(category='animals').filter(
    answer_a__icontains='balon'
)
print('Krivih pitanja:', wrong.count())
for q in wrong[:5]:
    print(q.question_text, '|', q.category, '|', q.answer_a)
"
```

Fix: ili popraviti kategoriju u DB ili u seed skripti.

---

## NAPOMENA ZA JAVA REKREACIJU
Sve ove greške su klasični web → mobile propusti:
1. iOS Safari touch eventi zahtijevaju explicit handling
2. Type coercion (== vs ===) uvijek koristiti strict usporedbu
3. Seed podaci moraju imati integrity check (kategorija ≠ sadržaj)
Ove lekcije vrijede bez obzira na stack.

