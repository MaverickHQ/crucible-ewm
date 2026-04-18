from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaceBuy:
    symbol: str
    quantity: float
    price: float

    def to_dict(self) -> dict:
        return {
            "type": "PlaceBuy",
            "symbol": self.symbol,
            "quantity": self.quantity,
            "price": self.price,
        }


@dataclass(frozen=True)
class PlaceSell:
    symbol: str
    quantity: float
    price: float

    def to_dict(self) -> dict:
        return {
            "type": "PlaceSell",
            "symbol": self.symbol,
            "quantity": self.quantity,
            "price": self.price,
        }
