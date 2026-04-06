"""
core/db_routers.py — Django Database Router za višebaznu arhitekturu

Baze:
  default      → fina_erp     (LIMIT Connect ERP, svi dosadašnji modeli)
  memio_pets   → memio_pets   (Memio.pet — ljubimci, uzgajivači, lanac vlasništva)
  memio_world  → memio_world  (Memio.world — digitalna baština, TimeCapsule, sjećanja)

Pravilo: app_label određuje bazu. Nema cross-baza FK-ova.
"""


MEMIO_PET_APPS = {'memio_pet'}
MEMIO_WORLD_APPS = {'memio_world'}

# Unija svih ne-default app_label-ova
_ROUTED_APPS = {
    'memio_pet': 'memio_pets',
    'memio_world': 'memio_world',
    'memio_farm': 'memio_farm',
}


class MultiDbRouter:
    """
    Univerzalni router za sve 3 baze.
    app_label → baza mapping. Sve ostalo ide u default (fina_erp).
    """

    def _db_for(self, model):
        return _ROUTED_APPS.get(model._meta.app_label)

    def db_for_read(self, model, **hints):
        return self._db_for(model)

    def db_for_write(self, model, **hints):
        return self._db_for(model)

    def allow_relation(self, obj1, obj2, **hints):
        """
        Dozvoli relacije unutar iste baze.
        Zabrani cross-baza relacije.
        """
        db1 = _ROUTED_APPS.get(obj1._meta.app_label, 'default')
        db2 = _ROUTED_APPS.get(obj2._meta.app_label, 'default')
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        target_db = _ROUTED_APPS.get(app_label)
        if target_db:
            return db == target_db
        # Non-routed apps samo u default
        if db in ('memio_pets', 'memio_world', 'memio_farm'):
            return False
        return None


# Backward compatibility alias
MemioPetsRouter = MultiDbRouter
