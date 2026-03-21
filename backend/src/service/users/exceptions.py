from core.errors import BadRequestError, NotFoundError, PayloadTooLargeError, UnauthorizedError


class NotAuthenticated(UnauthorizedError):
    error_code = "NOT_AUTHENTICATED"
    default_detail = "Not authenticated"


class UnsupportedAvatarContentTypeError(BadRequestError):
    error_code = "UNSUPPORTED_AVATAR_CONTENT_TYPE"

    def __init__(self, allowed: list[str]) -> None:
        allowed_list = ", ".join(sorted(allowed))
        super().__init__(detail=f"Unsupported avatar content type. Allowed: {allowed_list}")


class InvalidAvatarObjectKeyError(BadRequestError):
    error_code = "INVALID_AVATAR_OBJECT_KEY"
    default_detail = "Invalid avatar object key"


class AvatarObjectNotFoundError(BadRequestError):
    error_code = "AVATAR_OBJECT_NOT_FOUND"
    default_detail = "Avatar object not found in storage"


class AvatarUnsupportedContentTypeError(BadRequestError):
    error_code = "AVATAR_OBJECT_UNSUPPORTED_CONTENT_TYPE"
    default_detail = "Uploaded object has unsupported content type"


class AvatarTooLargeError(PayloadTooLargeError):
    error_code = "AVATAR_TOO_LARGE"

    def __init__(self, max_size_mb: int) -> None:
        super().__init__(detail=f"Avatar file too large. Max {max_size_mb} MB")


class InvalidCursorError(BadRequestError):
    error_code = "INVALID_CURSOR"
    default_detail = "Invalid cursor"


class UnknownRolesError(NotFoundError):
    error_code = "UNKNOWN_ROLES"

    def __init__(self, missing_roles: list[str]) -> None:
        missing_sorted = ", ".join(sorted(missing_roles))
        super().__init__(detail=f"Unknown roles: {missing_sorted}")


class UserNotFoundError(NotFoundError):
    error_code = "USER_NOT_FOUND"
    default_detail = "User not found"
