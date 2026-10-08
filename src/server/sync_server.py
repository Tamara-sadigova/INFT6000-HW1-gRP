from concurrent import futures
import grpc

# Import generated Protobuf code from proto/
import proto.rental_pb2 as pb2
import proto.rental_pb2_grpc as pb2_grpc

# Import Member 1's OOP classes and exceptions
from src.oop.exceptions import (
    BookNotFoundError,
    InvalidOperationError,
    OutOfStockError,
    RentalLimitExceededError,
    RentalNotFoundError,
)
from src.oop.rental_manager import RentalManager
from src.oop.sample_data import create_sample_catalog


class TextbookRentalServicer(pb2_grpc.TextbookRentalServiceServicer):
    def __init__(self):
        # Initialize catalog with sample data and connect to RentalManager
        self.catalog = create_sample_catalog()
        self.rental_manager = RentalManager(self.catalog)

    def CheckStock(self, request, context):
        try:
            stock = self.catalog.check_stock(request.isbn)
            available = self.catalog.is_available(request.isbn)
            return pb2.StockResponse(exists=True, stock=stock, is_available=available)
        except BookNotFoundError:
            return pb2.StockResponse(exists=False, stock=0, is_available=False)

    def GetBook(self, request, context):
        try:
            book = self.catalog.get_book(request.isbn)
            return pb2.BookResponse(
                isbn=book.isbn,
                title=book.title,
                author=book.author,
                price_per_day=book.price_per_day,
                stock=book.stock,
                is_available=book.is_available,
            )
        except BookNotFoundError as e:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details(str(e))
            return pb2.BookResponse()

    def SearchBooks(self, request, context):
        matching_books = self.catalog.search(request.query)
        book_responses = [
            pb2.BookResponse(
                isbn=b.isbn,
                title=b.title,
                author=b.author,
                price_per_day=b.price_per_day,
                stock=b.stock,
                is_available=b.is_available,
            )
            for b in matching_books
        ]
        return pb2.SearchResponse(books=book_responses)

    def RentBook(self, request, context):
        try:
            days = request.days if request.days > 0 else RentalManager.DEFAULT_RENTAL_DAYS
            rental = self.rental_manager.rent_book(
                student_id=request.student_id,
                isbn=request.isbn,
                days=days,
            )
            return pb2.RentResponse(
                success=True,
                rental_id=rental.rental_id,
                total_price=rental.total_price,
                message="Rental created successfully",
            )
        except (
            BookNotFoundError,
            OutOfStockError,
            RentalLimitExceededError,
            InvalidOperationError,
        ) as e:
            return pb2.RentResponse(
                success=False,
                rental_id="",
                total_price=0.0,
                message=str(e),
            )

    def ReturnBook(self, request, context):
        try:
            self.rental_manager.return_book(request.rental_id)
            return pb2.ReturnResponse(
                success=True,
                message="Book returned successfully",
            )
        except (RentalNotFoundError, InvalidOperationError) as e:
            return pb2.ReturnResponse(
                success=False,
                message=str(e),
            )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_TextbookRentalServiceServicer_to_server(
        TextbookRentalServicer(), server
    )
    server.add_insecure_port("[::]:50051")
    print("gRPC server running on port 50051...")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()