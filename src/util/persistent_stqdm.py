from stqdm import stqdm


class PersistentSTQDM(stqdm):
    """
    Overriding the st_clear() method, so that the text and progress bar are still displayed after close() is called.
    """

    def st_clear(self):
        pass

    def close(self):
        super().close()
