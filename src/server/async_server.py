import asyncio

import grpc

import proto.rental_pb2 as pb2
import proto.rental_pb2_grpc as pb2_grpc

from src.oop.exceptions import (
    BookNotFoundError,
    InvalidOperationError,
    OutOfStockError,
    RentalLimitExceededError,
    RentalNotFoundError,
)
from src.oop.rental_manager import RentalManager
from src.oop.sample_data import create_sample_catalog

SEARCH_DELAY = 0.5   # simulated slow search so the async benefit is visible


def book_to_pb(b):
    return pb2.BookResponse(
        isbn=b.isbn, title=b.title, author=b.author,
        price_per_day=b.price_per_day, stock=b.stock, is_available=b.is_available,
    )


class AsyncTextbookRentalServicer(pb2_grpc.TextbookRentalServiceServicer):
    def __init__(self):
        self.catalog = create_sample_catalog()
        self.rental_manager = RentalManager(self.catalog)

    async def CheckStock(self, request, context):
        try:
            stock = self.catalog.check_stock(request.isbn)
            available = self.catalog.is_available(request.isbn)
            return pb2.StockResponse(exists=True, stock=stock, is_available=available)
        except BookNotFoundError:
            return pb2.StockResponse(exists=False, stock=0, is_available=False)

    async def GetBook(self, request, context):
        try:
            return book_to_pb(self.catalog.get_book(request.isbn))
        except BookNotFoundError as e:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(e))

    async def SearchBooks(self, request, context):
        await asyncio.sleep(SEARCH_DELAY)      # does NOT block the event loop
        books = self.catalog.search(request.query)
        return pb2.SearchResponse(books=[book_to_pb(b) for b in books])

    async def RentBook(self, request, context):
        try:
            days = request.days if request.days > 0 else RentalManager.DEFAULT_RENTAL_DAYS
            rental = self.rental_manager.rent_book(
                student_id=request.student_id, isbn=request.isbn, days=days)
            return pb2.RentResponse(
                success=True, rental_id=rental.rental_id,
                total_price=rental.total_price, message="Rental created successfully")
        except (BookNotFoundError, OutOfStockError,
                RentalLimitExceededError, InvalidOperationError) as e:
            return pb2.RentResponse(success=False, rental_id="",
                                    total_price=0.0, message=str(e))

    async def ReturnBook(self, request, context):
        try:
            self.rental_manager.return_book(request.rental_id)
            return pb2.ReturnResponse(success=True, message="Book returned successfully")
        except (RentalNotFoundError, InvalidOperationError) as e:
            return pb2.ReturnResponse(success=False, message=str(e))

    async def ListRentals(self, request, context):
        rentals = self.rental_manager.get_student_rentals(request.student_id)
        infos = [
            pb2.RentalInfo(
                rental_id=r.rental_id, student_id=r.student_id, isbn=r.isbn,
                days=r.days, total_price=r.total_price, status=r.status.value,
                due_date=r.due_date.strftime("%Y-%m-%d"),
            )
            for r in rentals
        ]
        return pb2.RentalListResponse(rentals=infos)


async def serve():
    server = grpc.aio.server()
    pb2_grpc.add_TextbookRentalServiceServicer_to_server(
        AsyncTextbookRentalServicer(), server)
    server.add_insecure_port("[::]:50052")
    await server.start()
    print("Async gRPC server running on port 50052...")
    await server.wait_for_termination()


if __name__ == "__main__":
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        print("Async server stopped")