class BusinessRuleError(Exception):
    """Raised when an operation violates a business rule.

    Views turn this into a flash message (templates) or HTTP 400 (API).
    """
