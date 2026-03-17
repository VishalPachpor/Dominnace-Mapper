"""
Centralized exception hierarchy for the execution layer.

All pre-broker validation failures raise ExecutionValidationError which:
  - Carries a machine-readable `code` (stored in Trade.reject_reason)
  - Carries a human-readable `message` (shown in UI / Telegram)
  - Is caught in trade_manager.py before any MetaApi call is made
"""


class ExecutionValidationError(Exception):
    """
    Raised when a trade order fails pre-broker validation.
    The error is caught, logged to the trades table, and never
    allowed to bubble up as an unhandled crash.

    Example:
        raise ExecutionValidationError("INVALID_SL", "SL too close to entry for broker spec")
    """

    def __init__(self, code: str, message: str = None):
        self.code = code
        self.message = message or code
        super().__init__(self.message)

    def __str__(self):
        return f"[PRE_VALIDATION:{self.code}] {self.message}"


class BrokerAdapterError(Exception):
    """
    Raised when the execution adapter cannot fetch broker specifications
    (e.g., MetaApi timeout or unexpected response schema).
    Distinct from ExecutionValidationError to allow different retry logic.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
