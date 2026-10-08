class RentalHubError(Exception):
    pass


class BookNotFoundError(RentalHubError):
    def __init__(self, isbn):
        super().__init__(f"Book with ISBN '{isbn}' was not found")
        self.isbn = isbn


class DuplicateBookError(RentalHubError):
    def __init__(self, isbn):
        super().__init__(f"Book with ISBN '{isbn}' already exists")
        self.isbn = isbn


class OutOfStockError(RentalHubError):
    def __init__(self, isbn):
        super().__init__(f"Book with ISBN '{isbn}' is out of stock")
        self.isbn = isbn


class RentalNotFoundError(RentalHubError):
    def __init__(self, rental_id):
        super().__init__(f"Rental '{rental_id}' was not found")
        self.rental_id = rental_id


class RentalLimitExceededError(RentalHubError):
    def __init__(self, student_id, limit):
        super().__init__(f"Student '{student_id}' has reached the limit of {limit} active rentals")
        self.student_id = student_id
        self.limit = limit


class InvalidOperationError(RentalHubError):
    pass
