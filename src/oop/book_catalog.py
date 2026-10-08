import threading
from copy import deepcopy

from .exceptions import BookNotFoundError, DuplicateBookError, InvalidOperationError, OutOfStockError
from .models import Book


class BookCatalog:
    def __init__(self):
        self._books = {}
        self._lock = threading.RLock()

    def add_book(self, isbn, title, author, price_per_day, stock=0):
        with self._lock:
            if isbn in self._books:
                raise DuplicateBookError(isbn)
            book = Book(isbn, title, author, float(price_per_day), int(stock))
            self._books[isbn] = book
            return deepcopy(book)

    def remove_book(self, isbn):
        with self._lock:
            self._require(isbn)
            return deepcopy(self._books.pop(isbn))

    def get_book(self, isbn):
        with self._lock:
            return deepcopy(self._require(isbn))

    def list_books(self, only_available=False):
        with self._lock:
            books = self._books.values()
            if only_available:
                books = [b for b in books if b.is_available]
            return [deepcopy(b) for b in books]

    def search(self, query):
        with self._lock:
            if not query or not query.strip():
                return self.list_books()
            return [deepcopy(b) for b in self._books.values() if b.matches(query)]

    def check_stock(self, isbn):
        with self._lock:
            return self._require(isbn).stock

    def is_available(self, isbn):
        with self._lock:
            return self._require(isbn).is_available

    def get_price(self, isbn):
        with self._lock:
            return self._require(isbn).price_per_day

    def update_price(self, isbn, new_price):
        with self._lock:
            if new_price < 0:
                raise InvalidOperationError("Price must not be negative")
            book = self._require(isbn)
            book.price_per_day = float(new_price)
            return deepcopy(book)

    def restock(self, isbn, quantity):
        with self._lock:
            if quantity <= 0:
                raise InvalidOperationError("Quantity must be positive")
            book = self._require(isbn)
            book.stock += quantity
            return book.stock

    def reserve_copy(self, isbn):
        with self._lock:
            book = self._require(isbn)
            if not book.is_available:
                raise OutOfStockError(isbn)
            book.stock -= 1
            return book.stock

    def release_copy(self, isbn):
        with self._lock:
            book = self._require(isbn)
            book.stock += 1
            return book.stock

    def __len__(self):
        with self._lock:
            return len(self._books)

    def __contains__(self, isbn):
        with self._lock:
            return isbn in self._books

    def _require(self, isbn):
        book = self._books.get(isbn)
        if book is None:
            raise BookNotFoundError(isbn)
        return book
