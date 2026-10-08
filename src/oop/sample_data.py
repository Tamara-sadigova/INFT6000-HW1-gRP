from .book_catalog import BookCatalog

SAMPLE_BOOKS = [
    ("978-0132350884", "Clean Code", "Robert C. Martin", 1.50, 4),
    ("978-0201633610", "Design Patterns", "Erich Gamma", 2.00, 3),
    ("978-0262033848", "Introduction to Algorithms", "Thomas H. Cormen", 2.50, 5),
    ("978-0132126953", "Computer Networks", "Andrew S. Tanenbaum", 1.80, 2),
    ("978-1543057386", "Distributed Systems", "Maarten van Steen", 2.20, 3),
    ("978-0596007126", "Head First Design Patterns", "Eric Freeman", 1.20, 1),
    ("978-1449373320", "Designing Data-Intensive Applications", "Martin Kleppmann", 2.40, 2),
    ("978-0134685991", "Effective Java", "Joshua Bloch", 1.70, 0),
]


def create_sample_catalog():
    catalog = BookCatalog()
    for isbn, title, author, price, stock in SAMPLE_BOOKS:
        catalog.add_book(isbn, title, author, price, stock)
    return catalog
