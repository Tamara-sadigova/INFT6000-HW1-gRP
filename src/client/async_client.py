import asyncio
import time

import grpc

import proto.rental_pb2 as pb2
import proto.rental_pb2_grpc as pb2_grpc

TARGET = "localhost:50052"
QUERIES = ["clean", "design", "algorithms", "networks", "distributed"]
NETWORKS_ISBN = "978-0132126953"   # Computer Networks, stock 2


async def search(stub, query):
    reply = await stub.SearchBooks(pb2.SearchRequest(query=query), timeout=10)
    return query, [b.title for b in reply.books]


async def rent(stub, student_id):
    try:
        reply = await stub.RentBook(
            pb2.RentRequest(student_id=student_id, isbn=NETWORKS_ISBN, days=7),
            timeout=10)
        return f"{student_id}: success={reply.success} - {reply.message}"
    except grpc.aio.AioRpcError as err:
        return f"{student_id}: {err.code().name} - {err.details()}"


async def main():
    async with grpc.aio.insecure_channel(TARGET) as channel:
        stub = pb2_grpc.TextbookRentalServiceStub(channel)

        print("=== 1. Concurrent searches (asyncio.gather) ===")
        start = time.perf_counter()
        results = await asyncio.gather(*(search(stub, q) for q in QUERIES))
        concurrent_time = time.perf_counter() - start
        for q, titles in results:
            print(f"  '{q}': {titles}")
        print(f"Total time (concurrent): {concurrent_time:.2f}s")

        print("=== 2. Same searches, one after another (await in a loop) ===")
        start = time.perf_counter()
        for q in QUERIES:
            await search(stub, q)
        sequential_time = time.perf_counter() - start
        print(f"Total time (sequential): {sequential_time:.2f}s")
        print(f"Speed-up: {sequential_time / concurrent_time:.1f}x")

        print("=== 3. Concurrent rentals (stock = 2, 4 students) ===")
        outcomes = await asyncio.gather(*(rent(stub, f"S{i}") for i in range(1, 5)))
        for line in outcomes:
            print("  " + line)

        print("=== 4. ListRentals for S1 ===")
        reply = await stub.ListRentals(pb2.StudentRequest(student_id="S1"), timeout=10)
        print(f"  S1 active rentals: {len(reply.rentals)}")


if __name__ == "__main__":
    asyncio.run(main())