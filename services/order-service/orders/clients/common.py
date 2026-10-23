

class DownstreamUnavailable(Exception):
    """Raised when a dependent service cannot be used."""


class InventoryReservationRejected(Exception):
    """Raised when Inventory rejects a stock reservation."""