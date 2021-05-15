import asyncio
from . import async_task
from .async_executor import AsyncExecutor

async def do():
    futs = []
    futs.append(async_task.example_func("1"))
    futs.append(async_task.example_func("2"))
    futs.append(async_task.example_func2("1"))
    futs.append(async_task.example_func2("2"))
    await asyncio.sleep(1)
    futs.append(async_task.example_func("3"))
    futs.append(async_task.example_func("4"))
    futs.append(async_task.example_func2("3"))
    futs.append(async_task.example_func2("4"))
    await asyncio.gather(*futs)

async def main():
    async with AsyncExecutor:
        await do()



asyncio.run(main())
