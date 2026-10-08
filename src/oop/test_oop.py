import threading
import unittest
from datetime import datetime, timedelta

from src.oop import (
    BookCatalog,
    BookNotFoundError,
    DuplicateBookError,
    InvalidOperationError,
    OutOfStockError,
    RentalLimitExceededError,
    RentalManager,
    RentalNotFoundError,
    RentalStatus,
    create_sample_catalog,
)


class BookCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = BookCatalog()
        self.catalog.add_book("111", "Clean Code", "Robert Martin", 1.5, 2)
        self.catalog.add_book("222", "Effective Java", "Joshua Bloch", 2.0, 0)

    def test_add_and_get(self):
        book = self.catalog.get_book("111")
        self.assertEqual(book.title, "Clean Code")
        self.assertEqual(len(self.catalog), 2)
        self.assertIn("111", self.catalog)

    def test_duplicate_book(self):
        with self.assertRaises(DuplicateBookError):
            self.catalog.add_book("111", "Other", "Someone", 1.0, 1)

    def test_missing_book(self):
        with self.assertRaises(BookNotFoundError):
            self.catalog.check_stock("999")

    def test_stock_and_availability(self):
        self.assertEqual(self.catalog.check_stock("111"), 2)
        self.assertTrue(self.catalog.is_available("111"))
        self.assertFalse(self.catalog.is_available("222"))

    def test_search(self):
        self.assertEqual(len(self.catalog.search("clean")), 1)
        self.assertEqual(len(self.catalog.search("bloch")), 1)
        self.assertEqual(len(self.catalog.search("")), 2)
        self.assertEqual(len(self.catalog.search("python")), 0)

    def test_only_available(self):
        self.assertEqual(len(self.catalog.list_books(only_available=True)), 1)

    def test_reserve_and_release(self):
        self.catalog.reserve_copy("111")
        self.catalog.reserve_copy("111")
        with self.assertRaises(OutOfStockError):
            self.catalog.reserve_copy("111")
        self.catalog.release_copy("111")
        self.assertEqual(self.catalog.check_stock("111"), 1)

    def test_price_and_restock(self):
        self.catalog.update_price("111", 3.0)
        self.assertEqual(self.catalog.get_price("111"), 3.0)
        self.assertEqual(self.catalog.restock("222", 5), 5)
        with self.assertRaises(InvalidOperationError):
            self.catalog.restock("222", 0)

    def test_returned_copy_is_isolated(self):
        book = self.catalog.get_book("111")
        book.stock = 100
        self.assertEqual(self.catalog.check_stock("111"), 2)


class RentalManagerTests(unittest.TestCase):
    def setUp(self):
        self.catalog = create_sample_catalog()
        self.manager = RentalManager(self.catalog, max_active_rentals=2)
        self.isbn = "978-0132350884"

    def test_rent_book(self):
        rental = self.manager.rent_book("S1", self.isbn, 10)
        self.assertEqual(rental.status, RentalStatus.ACTIVE)
        self.assertEqual(rental.total_price, 15.0)
        self.assertEqual(self.catalog.check_stock(self.isbn), 3)

    def test_return_book(self):
        rental = self.manager.rent_book("S1", self.isbn)
        returned = self.manager.return_book(rental.rental_id)
        self.assertEqual(returned.status, RentalStatus.RETURNED)
        self.assertEqual(self.catalog.check_stock(self.isbn), 4)
        with self.assertRaises(InvalidOperationError):
            self.manager.return_book(rental.rental_id)

    def test_out_of_stock(self):
        with self.assertRaises(OutOfStockError):
            self.manager.rent_book("S1", "978-0134685991")

    def test_rental_limit(self):
        self.manager.rent_book("S1", self.isbn)
        self.manager.rent_book("S1", self.isbn)
        with self.assertRaises(RentalLimitExceededError):
            self.manager.rent_book("S1", self.isbn)
        self.assertEqual(len(self.manager.rent_book("S2", self.isbn).isbn), len(self.isbn))

    def test_invalid_input(self):
        with self.assertRaises(InvalidOperationError):
            self.manager.rent_book("", self.isbn)
        with self.assertRaises(InvalidOperationError):
            self.manager.rent_book("S1", self.isbn, 0)
        with self.assertRaises(BookNotFoundError):
            self.manager.rent_book("S1", "000")
        with self.assertRaises(RentalNotFoundError):
            self.manager.get_rental("NOPE")

    def test_student_rentals(self):
        rental = self.manager.rent_book("S1", self.isbn)
        self.manager.rent_book("S2", self.isbn)
        self.manager.return_book(rental.rental_id)
        self.assertEqual(len(self.manager.get_student_rentals("S1")), 0)
        self.assertEqual(len(self.manager.get_student_rentals("S1", active_only=False)), 1)
        self.assertEqual(len(self.manager.list_active_rentals()), 1)

    def test_overdue(self):
        self.manager.rent_book("S1", self.isbn, 5)
        later = datetime.now() + timedelta(days=6)
        self.assertEqual(len(self.manager.list_overdue_rentals(later)), 1)
        self.assertEqual(len(self.manager.list_overdue_rentals()), 0)

    def test_concurrent_rentals_do_not_oversell(self):
        manager = RentalManager(self.catalog, max_active_rentals=100)
        isbn = "978-0262033848"
        successes = []

        def worker(i):
            try:
                manager.rent_book(f"S{i}", isbn)
                successes.append(i)
            except OutOfStockError:
                pass

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(successes), 5)
        self.assertEqual(self.catalog.check_stock(isbn), 0)


if __name__ == "__main__":
    unittest.main()
