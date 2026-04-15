# WORKSPACE FILTER — AKTIVNO
**Executor: CC Opus | Status: 🔄**

## PROBLEM
Umbrella dashboard prikazuje SVE komitente svim radnicima.
Ljiljana vidi 75 komitenata, a treba 14 (svoj stol).

## RJEŠENJE
1. Dodaj workspace filter u umbrella_dashboard view
2. Non-admin korisnici automatski vide SAMO svoj workspace
3. Admin (Marija) vidi sve + dropdown za odabir stola
4. Komitent na više "mjesta" = M2M ostaje (Workspace.clients)
