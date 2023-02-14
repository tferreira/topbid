""" Scheduler """

import threading
import time
from collections.abc import Callable


class RepeatEvery(threading.Thread):
    """Calls a function on a defined interval"""

    def __init__(self, interval: float, func: Callable, *args, **kwargs):
        threading.Thread.__init__(self)
        self.interval = interval
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.runable = True

    def run(self):
        """Starts the scheduler"""
        while self.runable:
            # Sleeping beforehand, letting time for dependencies to startup
            time.sleep(self.interval)
            self.func(*self.args, **self.kwargs)

    def stop(self):
        """Stops the scheduler"""
        self.runable = False
