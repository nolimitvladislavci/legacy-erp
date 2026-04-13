# DIO 1: Exception Handling — Progress Tracker
# Started: 2026-04-13 ~09:30 UTC

## Baseline: 3,598 broad catches

## Strategy: 
- Focus on `except: pass` (silent swallows) FIRST — worst pattern
- Then `except Exception: pass` 
- Then `except Exception as e:` without logging
- Skip test files, management commands (lower priority)
- Skip backups/, tmp/, simulation/ (not production code)

## Progress:
- [ ] Phase 1: Kill all bare `except:` (11 instances)
- [ ] Phase 2: core/ — biggest offender (917)  
- [ ] Phase 3: pos/ (328)
- [ ] Phase 4: worktime/ + invoicing/ + accounts/ (406)
- [ ] Phase 5: konto/ + documents/ + appointments/ (238)
- [ ] Phase 6: remaining apps
