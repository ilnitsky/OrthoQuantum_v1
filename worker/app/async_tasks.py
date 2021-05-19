import time

from .executor import AsyncExecute

@AsyncExecute.in_thread(max_running=2)
def example_func(*args, **kwargs):
    print("START_T",args, kwargs)
    time.sleep(3)
    print("DONE_T", args, kwargs)

@AsyncExecute.in_process(max_running=1)
def example_func2(*args, **kwargs):
    print("START_P",args, kwargs)
    time.sleep(5)
    print("DONE_P", args, kwargs)
