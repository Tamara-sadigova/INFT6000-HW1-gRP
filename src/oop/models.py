from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class RentalStatus(Enum):
    ACTIVE = "ACTIVE"
    RETURNED = "RETURNED"


@dataclass
class Book:
    isbn: str
    title: str
    author: str
    price_per_day: float
    stock: int = 0

    def __post_init__(self):
        if not self.isbn or not self.isbn.strip():
            raise ValueError("ISBN must not be empty")
        if not self.title or not self.title.strip():
            raise ValueError("Title must not be empty")
        if self.price_per_day < 0:
            raise ValueError("Price must not be negative")
        if self.stock < 0:
            raise ValueError("Stock must not be negative")

    @property
    def is_available(self):
        return self.stock > 0

    def matches(self, query):
        text = query.strip().lower()
        return text in self.title.lower() or text in self.author.lower() or text == self.isbn.lower()


@dataclass
class Rental:
    rental_id: str
    student_id: str
    isbn: str
    days: int
    total_price: float
    rented_at: datetime = field(default_factory=datetime.now)
    returned_at: Optional[datetime] = None

    @property
    def due_date(self):
        return self.rented_at + timedelta(days=self.days)

    @property
    def status(self):
        return RentalStatus.RETURNED if self.returned_at else RentalStatus.ACTIVE

    @property
    def is_active(self):
        return self.status is RentalStatus.ACTIVE

    def is_overdue(self, now=None):
        now = now or datetime.now()
        return self.is_active and now > self.due_date

    def mark_returned(self, when=None):
        self.returned_at = when or datetime.now()
