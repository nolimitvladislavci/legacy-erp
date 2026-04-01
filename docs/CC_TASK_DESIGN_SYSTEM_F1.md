# CC_TASK_DESIGN_SYSTEM_F1 — CSS Design System Faza 1

**Datum:** 2026-04-02
**Status:** F1 DONE (temelj + 1 refaktor demo)

---

## Dijagnoza

| Metrika | Prije | Poslije F1 |
|---------|-------|-----------|
| fenix-ui.css linija | 148 | 281 |
| Design system klasa | ~20 | ~90 |
| Template fajlova | 868 | 868 |
| Inline style atributa | 10,986 | ~10,900 |
| ai_inbox.html inline | 83 | 8 (demo) |

### Top 10 zagadjeni templatei (za F2)
1. dashboards/company_admin.html — 269 inline
2. pos/joker.html — 219
3. pos/quick.html — 183
4. companies/settings.html — 114
5. website/no_limit.html — 110
6. dashboards/superadmin.html — 106
7. konto/dashboard.html — 97
8. dashboards/intelligence.html — 85
9. documents/ai_inbox.html — ~~83~~ **8** (DONE)
10. documents/arhiva_list.html — 79

---

## Fenix UI Design System v2 — Katalog klasa

### Tipografija
`f-heading`, `f-heading-lg/md/sm`, `f-subtitle`, `f-label`, `f-meta`,
`f-value`, `f-value-lg/xl`, `f-link`, `f-gold`, `f-green`, `f-red`, `f-blue`, `f-amber`

### Layout
`f-container`, `f-flex`, `f-flex-col`, `f-flex-between`, `f-flex-wrap`,
`f-gap-sm`, `f-gap`, `f-gap-lg`, `f-flex-1`,
`f-grid-2`, `f-grid-3`, `f-grid-4`, `f-grid-auto`

### Kartice
`f-card`, `f-card-flat`, `f-card-gold`, `f-card-green`, `f-card-red`,
`f-hero`, `f-panel`, `f-panel-header`

### Tablice
`f-table`, `.td-right`, `.td-center`, `.td-mono`, `.td-amount`, `.td-muted`

### Forme
`f-input`, `f-select`, `f-form-group`, `f-form-label`

### Gumbi
`f-btn`, `f-btn-gold`, `f-btn-ghost`, `f-btn-green`, `f-btn-red`, `f-btn-blue`,
`f-btn-sm`, `f-btn-lg`

### Badge/Status
`f-badge`, `f-badge-success/warning/danger/info/gold`
`status-paid`, `status-pending`, `status-overdue`, `status-warning`

### AI
`f-ai-badge`, `f-confidence-high/medium/low`

### Dashboard
`f-kpi`, `f-kpi-value`, `f-kpi-label`, `f-kpi-row`,
`f-kpi-green`, `f-kpi-blue`, `f-kpi-red`, `f-stat-card`

### Navigacija
`f-filter-bar`, `f-filter-chip`, `f-filter-chip.active`

### Utilities
`f-text-center`, `f-text-right`, `f-mb-0/sm/lg`, `f-mt`, `f-p/p-sm`,
`f-hidden`, `f-truncate`, `f-nowrap`, `f-section`, `f-mb`

---

## Plan F2 (slijedeca sesija)

Refaktorirati preostalih 9 top zagadjenih templateta po istom principu:
- Zamjena inline style → fenix-ui klase
- Cilj: svaki template ispod 15 inline style-ova
- Estimacija: ~800 inline style eliminacija
