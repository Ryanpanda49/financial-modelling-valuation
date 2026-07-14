"""Project-specific exceptions."""


class FmvaError(Exception):
    """Base exception for the package."""


class ConfigurationError(FmvaError):
    """Raised when required configuration is invalid."""


class SecRequestError(FmvaError):
    """Raised when an SEC request cannot be completed."""


class CompanyNotFoundError(FmvaError):
    """Raised when a ticker or CIK cannot be resolved."""


class SecDataError(FmvaError):
    """Raised when an SEC payload is malformed or incomplete."""


class HistoricalDataError(FmvaError):
    """Raised when standardized history cannot safely initialize a forecast."""
