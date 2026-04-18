# PLAN_042 — Journal Entry UI (Konto Knjiženje Interface)

## Cilj
Alpine.js-powered journal entry interface za manuelno knjiženje. Bookkeeper unosi konto debit/kredit parove, sistem validira uravnoteženost, sprema u JournalEntry + JournalLine (iz PLAN_041).

## URL struktura
```
/hr/konto/knjizenja/           → JournalListView
/hr/konto/knjizenja/novo/      → JournalCreateView
/hr/konto/knjizenja/<uuid>/    → JournalDetailView
/hr/konto/knjizenja/<uuid>/edit/ → JournalEditView (samo draft)
/hr/konto/knjizenja/<uuid>/post/ → JournalPostView (POST, finalizira)
/hr/konto/knjizenja/<uuid>/storno/ → JournalReverseView (POST)
/hr/konto/api/search/          → AccountSearchView (HTMX autocomplete)
```

## Model pretpostavke (iz PLAN_041)
```python
JournalEntry:
  - id (UUID)
  - company FK
  - entry_number (auto: KNJ-2026-0001)
  - entry_date
  - description
  - status: draft | posted | reversed
  - source: manual | import | invoice | pos | payroll
  - reference (optional string — npr. broj fakture)
  - created_by FK User
  - lines: reverse FK JournalLine

JournalLine:
  - journal_entry FK
  - account FK Account
  - debit (Decimal 10,2) — default 0
  - credit (Decimal 10,2) — default 0
  - description (optional)
  - CONSTRAINT: NOT (debit > 0 AND credit > 0)
```

## View: JournalCreateView
```python
class JournalCreateView(TenantView):
    template_name = "konto/journal_form.html"
    permission_required = Permission.MANAGE_JOURNAL

    def get(self, request):
        return render(request, self.template_name, {
            "today": date.today().isoformat(),
            "entry_number_preview": JournalEntry.next_number(request.company),
        })

    def post(self, request):
        data = json.loads(request.body)
        # Validacija
        lines = data.get("lines", [])
        errors = self._validate(lines)
        if errors:
            return JsonResponse({"ok": False, "errors": errors}, status=400)

        with transaction.atomic():
            entry = JournalEntry.objects.create(
                company=request.company,
                entry_number=JournalEntry.next_number(request.company),
                entry_date=data["entry_date"],
                description=data["description"],
                reference=data.get("reference", ""),
                status="draft",
                source="manual",
                created_by=request.user,
            )
            for line in lines:
                JournalLine.objects.create(
                    journal_entry=entry,
                    account_id=line["account_id"],
                    debit=Decimal(str(line.get("debit", 0))),
                    credit=Decimal(str(line.get("credit", 0))),
                    description=line.get("description", ""),
                )

        return JsonResponse({
            "ok": True,
            "entry_id": str(entry.id),
            "redirect": reverse("konto:journal_detail", args=[entry.id]),
        })

    def _validate(self, lines):
        errors = []
        if len(lines) < 2:
            errors.append("Knjiženje mora imati najmanje 2 stavke.")
        total_debit = sum(Decimal(str(l.get("debit", 0))) for l in lines)
        total_credit = sum(Decimal(str(l.get("credit", 0))) for l in lines)
        if total_debit != total_credit:
            errors.append(f"Duguje ({total_debit}) ≠ Potražuje ({total_credit}). Razlika: {abs(total_debit - total_credit)}")
        for i, line in enumerate(lines):
            if not line.get("account_id"):
                errors.append(f"Stavka {i+1}: konto nije odabran.")
            d = Decimal(str(line.get("debit", 0)))
            c = Decimal(str(line.get("credit", 0)))
            if d > 0 and c > 0:
                errors.append(f"Stavka {i+1}: ne može imati i duguje i potražuje.")
            if d == 0 and c == 0:
                errors.append(f"Stavka {i+1}: duguje ili potražuje mora biti > 0.")
        return errors
```

## View: AccountSearchView (HTMX autocomplete)
```python
class AccountSearchView(TenantView):
    def get(self, request):
        q = request.GET.get("q", "").strip()
        accounts = Account.objects.filter(
            Q(code__istartswith=q) | Q(name__icontains=q),
            company=request.company,
            is_active=True,
        ).order_by("code")[:20]
        results = [{"id": str(a.id), "code": a.code, "name": a.name} for a in accounts]
        return JsonResponse({"results": results})
```

## View: JournalPostView
```python
class JournalPostView(TenantView):
    permission_required = Permission.MANAGE_JOURNAL

    def post(self, request, pk):
        entry = get_object_or_404(JournalEntry, id=pk, company=request.company)
        if entry.status != "draft":
            return JsonResponse({"ok": False, "error": "Samo draft može biti knjižen."}, status=400)
        entry.status = "posted"
        entry.posted_at = timezone.now()
        entry.posted_by = request.user
        entry.save()
        messages.success(request, f"Knjiženje {entry.entry_number} je proknjiženo.")
        return JsonResponse({"ok": True, "redirect": reverse("konto:journal_detail", args=[entry.id])})
```

## View: JournalReverseView (storno)
```python
class JournalReverseView(TenantView):
    permission_required = Permission.MANAGE_JOURNAL

    def post(self, request, pk):
        original = get_object_or_404(JournalEntry, id=pk, company=request.company, status="posted")
        with transaction.atomic():
            storno = JournalEntry.objects.create(
                company=request.company,
                entry_number=JournalEntry.next_number(request.company),
                entry_date=date.today(),
                description=f"STORNO: {original.entry_number} — {original.description}",
                reference=original.entry_number,
                status="posted",
                source="manual",
                created_by=request.user,
                reversal_of=original,
            )
            for line in original.lines.all():
                JournalLine.objects.create(
                    journal_entry=storno,
                    account=line.account,
                    debit=line.credit,   # zamjena
                    credit=line.debit,   # zamjena
                    description=f"Storno: {line.description}",
                )
            original.status = "reversed"
            original.reversed_by = storno
            original.save()
        messages.success(request, f"Storno knjiženje {storno.entry_number} kreirano.")
        return redirect("konto:journal_detail", pk=storno.id)
```

## Template: konto/journal_form.html
Alpine.js komponenta `journalForm`:

```html
<div x-data="journalForm()" x-init="init()">
  <!-- Header -->
  <div class="card mb-4">
    <div class="grid grid-cols-3 gap-4">
      <div>
        <label class="label">Datum</label>
        <input type="date" x-model="entryDate" class="input" :max="today">
      </div>
      <div>
        <label class="label">Opis knjiženja</label>
        <input type="text" x-model="description" class="input" placeholder="npr. Plaćanje računa dobavljača">
      </div>
      <div>
        <label class="label">Referenca (opcija)</label>
        <input type="text" x-model="reference" class="input" placeholder="npr. R1-2026-0042">
      </div>
    </div>
  </div>

  <!-- Stavke -->
  <div class="card">
    <table class="table">
      <thead>
        <tr>
          <th class="w-40">Konto</th>
          <th>Naziv konta</th>
          <th class="w-32 text-right">Duguje (D)</th>
          <th class="w-32 text-right">Potražuje (P)</th>
          <th class="w-64">Opis stavke</th>
          <th class="w-10"></th>
        </tr>
      </thead>
      <tbody>
        <template x-for="(line, index) in lines" :key="line.id">
          <tr>
            <!-- Konto autocomplete -->
            <td>
              <div class="relative" x-data="accountSearch(line)">
                <input type="text"
                  x-model="line.accountCode"
                  @input.debounce.300="search($event.target.value)"
                  @keydown.enter.prevent="selectFirst()"
                  class="input font-mono"
                  placeholder="1000">
                <!-- Dropdown -->
                <div x-show="results.length > 0"
                     class="absolute z-50 bg-white border border-gray-200 rounded shadow-lg w-80 max-h-48 overflow-y-auto">
                  <template x-for="acc in results" :key="acc.id">
                    <div @click="select(acc, line)"
                         class="px-3 py-2 hover:bg-fenix-50 cursor-pointer text-sm">
                      <span class="font-mono text-fenix-700" x-text="acc.code"></span>
                      <span class="text-gray-600 ml-2" x-text="acc.name"></span>
                    </div>
                  </template>
                </div>
              </div>
            </td>
            <td>
              <span class="text-sm text-gray-600" x-text="line.accountName || '—'"></span>
            </td>
            <!-- Duguje -->
            <td>
              <input type="number" step="0.01" min="0"
                x-model="line.debit"
                @input="line.credit = line.debit > 0 ? 0 : line.credit; recalc()"
                class="input text-right font-mono"
                :class="{'border-red-400': line.debit > 0 && line.credit > 0}">
            </td>
            <!-- Potražuje -->
            <td>
              <input type="number" step="0.01" min="0"
                x-model="line.credit"
                @input="line.debit = line.credit > 0 ? 0 : line.debit; recalc()"
                class="input text-right font-mono">
            </td>
            <td>
              <input type="text" x-model="line.description" class="input" placeholder="Opis stavke">
            </td>
            <td>
              <button @click="removeLine(index)" class="text-red-400 hover:text-red-600" title="Ukloni">
                <svg class="w-4 h-4"><!-- trash icon --></svg>
              </button>
            </td>
          </tr>
        </template>
      </tbody>
      <tfoot>
        <tr class="bg-gray-50 font-semibold">
          <td colspan="2" class="text-right text-sm text-gray-500">UKUPNO:</td>
          <td class="text-right font-mono" :class="isBalanced ? 'text-green-600' : 'text-red-600'"
              x-text="formatCurrency(totalDebit)"></td>
          <td class="text-right font-mono" :class="isBalanced ? 'text-green-600' : 'text-red-600'"
              x-text="formatCurrency(totalCredit)"></td>
          <td colspan="2"></td>
        </tr>
      </tfoot>
    </table>

    <!-- Balance indicator -->
    <div class="mt-3 flex items-center gap-2" x-show="lines.length >= 2">
      <template x-if="isBalanced">
        <span class="badge-success">Uravnoteženo</span>
      </template>
      <template x-if="!isBalanced">
        <span class="badge-danger">Razlika: <strong x-text="formatCurrency(Math.abs(totalDebit - totalCredit))"></strong></span>
      </template>
    </div>

    <!-- Add line button -->
    <button @click="addLine()" class="btn-secondary mt-4">
      + Dodaj stavku
    </button>
  </div>

  <!-- Actions -->
  <div class="flex gap-3 mt-4">
    <button @click="save('draft')" class="btn-secondary" :disabled="saving">
      Spremi kao nacrt
    </button>
    <button @click="save('post')" class="btn-primary" :disabled="!isBalanced || saving">
      Proknjizi
    </button>
    <a href="{% url 'konto:journal_list' %}" class="btn-secondary">Odustani</a>
  </div>

  <!-- Error display -->
  <div x-show="errors.length > 0" class="alert-danger mt-4">
    <ul class="list-disc list-inside">
      <template x-for="err in errors" :key="err">
        <li x-text="err"></li>
      </template>
    </ul>
  </div>
</div>
```

## Alpine.js: journalForm()
```javascript
function journalForm() {
  return {
    entryDate: new Date().toISOString().slice(0, 10),
    description: '',
    reference: '',
    lines: [],
    errors: [],
    saving: false,

    init() {
      this.addLine();
      this.addLine();
    },

    addLine() {
      this.lines.push({
        id: Date.now() + Math.random(),
        account_id: null,
        accountCode: '',
        accountName: '',
        debit: '',
        credit: '',
        description: '',
      });
    },

    removeLine(index) {
      if (this.lines.length <= 2) return;
      this.lines.splice(index, 1);
    },

    get totalDebit() {
      return this.lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);
    },
    get totalCredit() {
      return this.lines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
    },
    get isBalanced() {
      return this.lines.length >= 2 &&
             Math.abs(this.totalDebit - this.totalCredit) < 0.001 &&
             this.totalDebit > 0;
    },

    recalc() { /* trigger Alpine reactivity */ },

    async save(action) {
      this.errors = [];
      this.saving = true;
      try {
        const resp = await fetch('/hr/konto/knjizenja/novo/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
          body: JSON.stringify({
            entry_date: this.entryDate,
            description: this.description,
            reference: this.reference,
            action: action,
            lines: this.lines.map(l => ({
              account_id: l.account_id,
              debit: parseFloat(l.debit) || 0,
              credit: parseFloat(l.credit) || 0,
              description: l.description,
            })),
          }),
        });
        const data = await resp.json();
        if (data.ok) {
          window.location.href = data.redirect;
        } else {
          this.errors = data.errors || [data.error];
        }
      } finally {
        this.saving = false;
      }
    },
    formatCurrency(val) {
      return new Intl.NumberFormat('hr-HR', { minimumFractionDigits: 2 }).format(val || 0) + ' EUR';
    },
  };
}

function accountSearch(line) {
  return {
    results: [],
    async search(q) {
      if (q.length < 2) { this.results = []; return; }
      const resp = await fetch(`/hr/konto/api/search/?q=${encodeURIComponent(q)}`);
      const data = await resp.json();
      this.results = data.results;
    },
    select(acc, line) {
      line.account_id = acc.id;
      line.accountCode = acc.code;
      line.accountName = acc.name;
      this.results = [];
    },
    selectFirst() {
      if (this.results.length > 0) this.select(this.results[0], this.$data);
    },
  };
}
```

## List view (JournalListView)
- Filter: datum od/do, status (draft/posted/reversed), konto (autocomplete)
- Tabela: entry_number | entry_date | description | D ukupno | P ukupno | status badge | actions
- HTMX paginacija (25 po stranici)
- Gumb "Novo knjiženje" (btn-primary)
- Row click → detail view

## Detail view
- Readonly prikaz stavki u tabeli
- Gumbi: "Proknjizi" (ako draft), "Storno" (ako posted), "Uredi" (ako draft)
- PDF export za tisak (WeasyPrint, A4 landscape)

## Template tag za konto prikaz
```python
@register.inclusion_tag("konto/tags/account_badge.html")
def account_badge(account):
    return {"account": account}
```
```html
<!-- account_badge.html -->
<span class="font-mono text-sm">{{ account.code }}</span>
<span class="text-gray-500 text-xs ml-1">{{ account.name }}</span>
```

## Permissions needed
```python
Permission.MANAGE_JOURNAL = "manage_journal"
# Dodati u PLAN_015 permission matrix
# Roles: owner, admin, accountant
```

## Testovi
```python
def test_journal_create_balanced(auth_client, company):
    # 2 linije, debit = credit → 201
    ...

def test_journal_unbalanced_rejected(auth_client, company):
    # debit != credit → 400 with error message
    ...

def test_journal_post_changes_status(auth_client, company):
    # draft → posted
    ...

def test_journal_reverse_creates_storno(auth_client, company):
    # posted → reversed + novi storno entry
    ...

def test_account_search_filters_by_company(auth_client, company):
    # ne vraća konta druge kompanije
    ...
```
