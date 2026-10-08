import threading
import uuid
from copy import deepcopy

from .book_catalog import BookCatalog
from .exceptions import InvalidOperationError, RentalLimitExceededError, RentalNotFoundError
from .models import Rental


class RentalManager:
    DEFAULT_RENTAL_DAYS = 14
    MAX_RENTAL_DAYS = 120

    def __init__(self, catalog: BookCatalog, max_active_rentals=3):
        if max_active_rentals <= 0:
            raise ValueError("max_active_rentals must be positive")
        self._catalog = catalog
        self._max_active_rentals = max_active_rentals
        self._rentals = {}
        self._lock = threading.RLock()

    @property
    def catalog(self):
        return self._catalog

    @property
    def max_active_rentals(self):
        return self._max_active_rentals

    def rent_book(self, student_id, isbn, days=DEFAULT_RENTAL_DAYS):
        if not student_id or not student_id.strip():
            raise InvalidOperationError("Student ID must not be empty")
        if days <= 0 or days > self.MAX_RENTAL_DAYS:
            raise InvalidOperationError(f"Rental days must be between 1 and {self.MAX_RENTAL_DAYS}")
        with self._lock:
            if self._count_active(student_id) >= self._max_active_rentals:
                raise RentalLimitExceededError(student_id, self._max_active_rentals)
            price = self._catalog.get_price(isbn)
            self._catalog.reserve_copy(isbn)
            rental = Rental(
                rental_id=uuid.uuid4().hex[:8].upper(),
                student_id=student_id,
                isbn=isbn,
                days=days,
                total_price=round(price * days, 2),
            )
            self._rentals[rental.rental_id] = rental
            return deepcopy(rental)

    def return_book(self, rental_id):
        with self._lock:
            rental = self._require(rental_id)
            if not rental.is_active:
                raise InvalidOperationError(f"Rental '{rental_id}' has already been returned")
            rental.mark_returned()
            self._catalog.release_copy(rental.isbn)
            return deepcopy(rental)

    def get_rental(self, rental_id):
        with self._lock:
            return deepcopy(self._require(rental_id))

    def get_student_rentals(self, student_id, active_only=True):
        with self._lock:
            return [
                deepcopy(r)
                for r in self._rentals.values()
                if r.student_id == student_id and (r.is_active or not active_only)
            ]

    def list_active_rentals(self):
        with self._lock:
            return [deepcopy(r) for r in self._rentals.values() if r.is_active]

    def list_overdue_rentals(self, now=None):
        with self._lock:
            return [deepcopy(r) for r in self._rentals.values() if r.is_overdue(now)]

    def _count_active(self, student_id):
        return sum(1 for r in self._rentals.values() if r.student_id == student_id and r.is_active)

    def _require(self, rental_id):
        rental = self._rentals.get(rental_id)
        if rental is None:
            raise RentalNotFoundError(rental_id)
        return rental
