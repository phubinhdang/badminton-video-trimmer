import logging
import time

from proglog import ProgressBarLogger

logger = logging.getLogger(__name__)


class MoviepyBarLogger(ProgressBarLogger):
    """
    Update the internal stdqm bar every time the call back is triggered by moviepy
    """

    def __init__(self, stqdm_bar, start_time: float):
        super().__init__()
        self.stqdm_bar = stqdm_bar  # Pass the stqdm instance here
        self.start_time = start_time

    def callback(self, **changes):
        super().callback()

    def bars_callback(self, bar, attr, value, old_value=None):
        pass
        total = self.bars.get(bar, {}).get('total', None)
        if total is not None and total > 0:
            # Update the stqdm bar with new progress
            if self.stqdm_bar is not None:
                elapsed_time = time.time() - self.start_time
                self.stqdm_bar.st_display(n=value, total=total, elapsed=elapsed_time)
        else:
            logger.error(f"Warning: Total not found for bar '{bar}'. Unable to update progress.")
