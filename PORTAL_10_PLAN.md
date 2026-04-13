# PORTAL 10/10 PLAN
> Start: 9.2/10 | Target: 10/10 | Date: 2026-04-13

## PHASE 1: Fix Test Infrastructure
- [x] pytest.ini: DJANGO_SETTINGS_MODULE = core.settings (was fina_connect.settings)
- [ ] Run full test suite, establish baseline pass/fail count
- [ ] Measure coverage baseline

## PHASE 2: Ruff Cleanup (225 → 0)
- [ ] Auto-fix 13 fixable errors
- [ ] Manual fix remaining 212 (F841 unused vars, F401 unused imports, F811 redefined, I001 unsorted)
- [ ] Target: 0 ruff errors

## PHASE 3: Test Coverage → 30%+
- [ ] core/ — models, managers, base views
- [ ] companies/ — settings, module registry
- [ ] accounts/ — auth, permissions
- [ ] invoicing/ — critical business logic
- [ ] Focus: model tests + view smoke tests

## PHASE 4: App Consolidation
- [ ] Identify ghost/unused apps (beyond fitness/insurance already done)
- [ ] Deactivate from INSTALLED_APPS
- [ ] Clean imports

## PHASE 5: OpenAPI Completeness
- [ ] Tag remaining ViewSets
- [ ] Schema descriptions for all endpoints

## PHASE 6: Final Score
- [ ] Django check: 0
- [ ] Ruff: 0
- [ ] mypy: clean on core/
- [ ] Coverage: 30%+
- [ ] Update FENIX_STATUS.md
