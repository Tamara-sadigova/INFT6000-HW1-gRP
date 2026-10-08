import grpc

import proto.rental_pb2 as pb2
import proto.rental_pb2_grpc as pb2_grpc

ISBN = "978-0132350884"   # Clean Code (stock 4)


def show_rentals(stub, student_id):
    reply = stub.ListRentals(pb2.StudentRequest(student_id=student_id), timeout=5)
    print(f"Active rentals of {student_id}: {len(reply.rentals)}")
    for r in reply.rentals:
        print(f"  {r.rental_id} | {r.isbn} | {r.days} days | "
              f"{r.total_price} | {r.status} | due {r.due_date}")


def main():
    with grpc.insecure_channel("localhost:50051") as channel:
        stub = pb2_grpc.TextbookRentalServiceStub(channel)

        print("=== 1. Check stock ===")
        stock = stub.CheckStock(pb2.StockRequest(isbn=ISBN), timeout=5)
        print(f"exists={stock.exists}, stock={stock.stock}, available={stock.is_available}")

        print("=== 2. Rent a book ===")
        rent = stub.RentBook(
            pb2.RentRequest(student_id="S100", isbn=ISBN, days=7), timeout=5)
        print(f"success={rent.success}, rental_id={rent.rental_id}, "
              f"price={rent.total_price}, message={rent.message}")

        print("=== 3. List active rentals (ListRentals) ===")
        show_rentals(stub, "S100")

        print("=== 4. Return the book ===")
        ret = stub.ReturnBook(pb2.ReturnRequest(rental_id=rent.rental_id), timeout=5)
        print(f"success={ret.success}, message={ret.message}")

        print("=== 5. List rentals again (should be empty) ===")
        show_rentals(stub, "S100")

        print("=== 6. Error handling ===")
        bad = stub.RentBook(
            pb2.RentRequest(student_id="S100", isbn="000", days=7), timeout=5)
        print(f"rent unknown book: success={bad.success}, message={bad.message}")
        try:
            stub.GetBook(pb2.BookRequest(isbn="000"), timeout=5)
        except grpc.RpcError as err:
            print(f"GetBook unknown: {err.code().name} - {err.details()}")


if __name__ == "__main__":
    main()