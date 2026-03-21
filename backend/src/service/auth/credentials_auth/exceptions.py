from core.errors import ConflictError, UnauthorizedError


class WrongCredentials(UnauthorizedError):
    error_code = "WRONG_CREDENTIALS"
    default_detail = "Wrong credentials passed"


class NotAuthenticated(UnauthorizedError):
    error_code = "NOT_AUTHENTICATED"
    default_detail = "Not authenticated"


class AlreadyExists(ConflictError):
    error_code = "USER_ALREADY_EXISTS"
    default_detail = "This email or phone number is already taken"
