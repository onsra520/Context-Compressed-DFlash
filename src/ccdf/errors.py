"""Domain-specific exceptions."""


class CCDFError(RuntimeError):
    """Base runtime error."""


class ConfigurationError(CCDFError):
    """Configuration is missing or internally inconsistent."""


class ModelContractError(CCDFError):
    """Loaded models do not satisfy the D-Flash contract."""


class MemoryBudgetError(CCDFError):
    """The D-Flash stack exceeded its reserved-memory gate."""


class ReferenceValidationError(CCDFError):
    """Runtime output diverged from the pinned deterministic reference path."""
