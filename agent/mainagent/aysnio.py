import asyncio
import time

async def download(name, seconds):
    print(f"{name} 开始下载")
    await asyncio.sleep(seconds)   # 假装等网络 I/O
    print(f"{name} 下载完成")

async def main():
    start = time.time()

    # 两个下载「同时等」，不是排队等
    await asyncio.gather(
        download("文件A", 2),
        download("文件B", 2),
    )

    print(f"总耗时: {time.time() - start:.1f} 秒")

asyncio.run(main())