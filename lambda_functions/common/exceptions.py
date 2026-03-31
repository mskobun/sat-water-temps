class NoDataError(Exception):
    """Raised when filtering leaves zero valid pixels."""
    def __init__(self, filter_stats):
        self.filter_stats = filter_stats
        super().__init__("No valid pixels after filtering")
