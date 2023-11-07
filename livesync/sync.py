import asyncio

from .folder import Folder


def sync(*args: Folder) -> None:
    tasks = []
    for folder in args:
        tasks.append(asyncio.create_task(folder.watch()))
        tasks.append(asyncio.create_task(folder.hold_mutex()))
    try:
        async def run_tasks():
            asyncio.gather(*tasks)
        asyncio.run(run_tasks())
    except KeyboardInterrupt:
        print('Bye!')
