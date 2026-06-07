from decimal import Decimal

class Currency:
    def __init__(self, code: str, minor_unit: int):
        self.code = code.upper()
        self.minor_unit = minor_unit  


CURRENCIES = {
    "EGP": Currency("EGP", 100),  
    "USD": Currency("USD", 100),  
    "JPY": Currency("JPY", 1),    
}


class Money:
    def __init__(self, amount_minor: int, currency: str):
        self.amount_minor = amount_minor
        self.currency = currency.upper()

    def currency_info(self):
        return CURRENCIES[self.currency]

    def __add__(self, other: "Money"):
        self._check_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: "Money"):
        self._check_currency(other)

        if self.amount_minor < other.amount_minor:
            raise ValueError("Insufficient balance")

        return Money(self.amount_minor - other.amount_minor, self.currency)

    def _check_currency(self, other):
        if self.currency != other.currency:
            raise ValueError("Currency mismatch")

    def __mul__(self, multiplier: float):
        return Money(int(self.amount_minor * multiplier), self.currency)
    
    def to_major(self):
        return self.amount_minor / self.currency_info().minor_unit

    @property
    def amount_major(self) -> Decimal:
        return Decimal(str(self.amount_minor)) / Decimal(str(self.currency_info().minor_unit))

    @classmethod
    def from_major(cls, amount_major: Decimal, currency: str) -> "Money":
        minor_unit = CURRENCIES[currency.upper()].minor_unit
        amount_minor = int(amount_major * Decimal(str(minor_unit)))
        return cls(amount_minor=amount_minor, currency=currency)

    def __repr__(self):
        return f"{self.to_major()} {self.currency}"