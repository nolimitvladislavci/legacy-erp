"""
data_migration/adapters/base.py

Bazni interfejs za sve adaptere.
Svaki adapter (CSV, Synesis, Luceed, Pantheon...) MORA naslijediti BaseAdapter
i implementirati sve apstraktne metode.
"""
from abc import ABC, abstractmethod
from typing import Any


class AdapterResult:
    """Standardizirani rezultat importa."""

    __slots__ = ("created", "updated", "skipped", "failed", "errors")

    def __init__(self):
        self.created: int = 0
        self.updated: int = 0
        self.skipped: int = 0
        self.failed: int = 0
        self.errors: list[dict] = []

    @property
    def total(self) -> int:
        return self.created + self.updated + self.skipped + self.failed

    def add_error(self, message: str, row: int | None = None,
                  field: str = "", value: str = ""):
        self.errors.append({
            "row": row,
            "field": field,
            "message": message,
            "value": str(value)[:500],
        })
        self.failed += 1

    def __repr__(self):
        return (
            f"AdapterResult(created={self.created}, updated={self.updated}, "
            f"skipped={self.skipped}, failed={self.failed})"
        )


class MappingField:
    """Definicija jednog polja za frontend mapiranje."""

    __slots__ = ("key", "label", "required", "hint", "field_type")

    def __init__(self, key: str, label: str, required: bool = False,
                 hint: str = "", field_type: str = "text"):
        self.key = key
        self.label = label
        self.required = required
        self.hint = hint
        self.field_type = field_type

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "required": self.required,
            "hint": self.hint,
            "field_type": self.field_type,
        }


class BaseAdapter(ABC):
    """
    Bazna klasa za sve import adaptere.

    Lifecycle:
        1. detect_format(file)     -> bool
        2. extract_raw_data(file)  -> list[dict]
        3. get_mapping_schema()    -> list[dict]
        4. execute_import(...)     -> AdapterResult
    """

    name: str = ""
    label: str = ""
    supported_formats: list[str] = []
    description: str = ""

    @abstractmethod
    def detect_format(self, file_path: str, file_format: str = "") -> bool:
        ...

    @abstractmethod
    def extract_raw_data(self, file_path: str) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_mapping_schema(self, entity_type: str = "partners") -> list[dict]:
        ...

    @abstractmethod
    def execute_import(
        self,
        company,
        data: list[dict[str, Any]],
        field_mapping: dict[str, str],
        entity_type: str = "partners",
        user=None,
    ) -> AdapterResult:
        ...

    def get_detected_columns(self, data: list[dict]) -> list[str]:
        if not data:
            return []
        columns = []
        seen = set()
        for row in data[:5]:
            for key in row.keys():
                if key not in seen:
                    columns.append(key)
                    seen.add(key)
        return columns

    def validate_mapping(self, field_mapping: dict[str, str],
                         entity_type: str = "partners") -> list[str]:
        schema = self.get_mapping_schema(entity_type)
        required_keys = {f["key"] for f in schema if f.get("required")}
        mapped_keys = set(field_mapping.values())
        missing = required_keys - mapped_keys
        return [f"Obavezno polje '{key}' nije mapirano." for key in sorted(missing)]

    def apply_mapping(self, data: list[dict], field_mapping: dict[str, str]) -> list[dict]:
        result = []
        for row in data:
            mapped_row = {}
            for src_col, erp_field in field_mapping.items():
                if src_col in row:
                    value = row[src_col]
                    if isinstance(value, str):
                        value = value.strip()
                    mapped_row[erp_field] = value
            result.append(mapped_row)
        return result


# ── Adapter Registry ──────────────────────────────────────────────

_registry: dict[str, type[BaseAdapter]] = {}


def register_adapter(adapter_class: type[BaseAdapter]):
    if not adapter_class.name:
        raise ValueError(f"{adapter_class.__name__} mora definirati 'name'")
    _registry[adapter_class.name] = adapter_class
    return adapter_class


def get_adapter(name: str) -> BaseAdapter:
    cls = _registry.get(name)
    if cls is None:
        raise KeyError(f"Adapter '{name}' nije registriran. Dostupni: {list(_registry.keys())}")
    return cls()


def get_all_adapters() -> list[BaseAdapter]:
    return [cls() for cls in _registry.values()]


def detect_adapter(file_path: str, file_format: str = "") -> BaseAdapter | None:
    for cls in _registry.values():
        adapter = cls()
        try:
            if adapter.detect_format(file_path, file_format):
                return adapter
        except (ValueError, KeyError):
            continue
    return None
