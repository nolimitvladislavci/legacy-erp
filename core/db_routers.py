"""
core/db_routers.py — Django Database Router za višebaznu arhitekturu

Baze:
  default      → fina_erp     (LIMIT Connect ERP, svi dosadašnji modeli)
  memio_pets   → memio_pets   (Memio.pet — ljubimci, uzgajivači, lanac vlasništva)

Pravilo: app_label određuje bazu. Nema cross-baza FK-ova.
"""


MEMIO_PET_APPS = {'memio_pet'}


class MemioPetsRouter:
    """
    Sve iz memio_pet app_label ide u memio_pets bazu.
    Sve ostalo ostaje u default (fina_erp).
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label in MEMIO_PET_APPS:
            return 'memio_pets'
        return None  # default

    def db_for_write(self, model, **hints):
        if model._meta.app_label in MEMIO_PET_APPS:
            return 'memio_pets'
        return None  # default

    def allow_relation(self, obj1, obj2, **hints):
        """
        Dozvoli relacije unutar iste baze.
        Zabrani cross-baza relacije (FK između memio_pet i ERP-a).
        """
        db1 = 'memio_pets' if obj1._meta.app_label in MEMIO_PET_APPS else 'default'
        db2 = 'memio_pets' if obj2._meta.app_label in MEMIO_PET_APPS else 'default'
        return db1 == db2

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in MEMIO_PET_APPS:
            return db == 'memio_pets'
        # Sve ostalo ide u default, ne u memio_pets
        if db == 'memio_pets':
            return False
        return None
