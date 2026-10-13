"""Zajednička greška za HTTP sloj ekrana (status, poruka na hrvatskom, dodatna polja za front-end)."""


class Greska(Exception):
    def __init__(self, status: int, poruka: str, **extra):
        super().__init__(poruka)
        self.status, self.poruka, self.extra = status, poruka, extra
