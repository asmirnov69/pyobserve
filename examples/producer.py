import asyncio
import random, time
from jupiterli import save_run_dets
from jupiterli import add_ts_point, add_serial_point

async def producer():
    while True:
        await asyncio.sleep(2.5/10)

        new_val = random.randint(1, 10)
        ts = time.time()

        add_ts_point("data1", ts, new_val)
        add_ts_point("data2", ts, new_val + 1.0)
        add_serial_point("data3", new_val + 10.0)
        print("Produced:", ts, new_val)

def main():
    asyncio.run(producer())

if __name__ == "__main__":
    save_run_dets(category = "examples/producer")
    main()
