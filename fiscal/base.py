from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class FiscalResult:
    success: bool
    zki: str = ''
    jir: str = ''
    tse_signature: str = ''
    tse_transaction_number: str = ''
    qr_code_data: str = ''
    error_message: str = ''
    raw_request: str = ''
    raw_response: str = ''


class BaseFiscalProvider(ABC):
    def __init__(self, config):
        self.config = config

    @abstractmethod
    def fiscalize(self, receipt_data: dict) -> FiscalResult:
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        pass

    @abstractmethod
    def echo(self) -> bool:
        pass
