class IntegrationError(Exception):
    """Missing credentials or external API failure in strict (non-mock) mode."""

    def __init__(self, message: str, source: str = ""):
        self.message = message
        self.source = source
        super().__init__(message)
