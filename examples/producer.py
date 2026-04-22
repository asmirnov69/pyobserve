import asyncio
import random, time
import redis

REDIS_URL = "redis://localhost"

async def producer():
    r = redis.from_url(REDIS_URL, decode_responses=True)

    while True:
        await asyncio.sleep(2.5/10)

        new_val = random.randint(1, 10)
        ts = time.time()

        r.xadd("data1", {"timestamp": ts, "value": new_val}, maxlen = 10000)
        r.xadd("data2", {"timestamp": ts, "value": new_val + 1.0}, maxlen = 10000)
        print("Produced:", ts, new_val)

def main():
    asyncio.run(producer())

if __name__ == "__main__":
    main()
