"""Custom error classes for bulk SEO generation workflow."""


class RetryableError(Exception):
    """Error that should be retried by Temporal."""
    pass


class NonRetryableError(Exception):
    """Error that should NOT be retried by Temporal."""
    pass
