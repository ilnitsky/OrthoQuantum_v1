import subprocess

from ..async_executor import async_pool

@async_pool.in_thread(max_running=4)
def do_blast(*args):
    # TODO: Lauch process to blast
    subprocess.run(["echo", "123"])
