"""Domain-specific exceptions."""


class Rec2Error(RuntimeError):
    """Base runtime error."""


class ConfigurationError(Rec2Error):
    """Configuration is missing or internally inconsistent."""


class ModelContractError(Rec2Error):
    """Loaded models do not satisfy the D-Flash contract."""


class MemoryBudgetError(Rec2Error):
    """The D-Flash stack exceeded its reserved-memory gate."""


class ReferenceValidationError(Rec2Error):
    """Rec-2 diverged from the pinned deterministic reference path."""
