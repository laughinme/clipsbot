from core.errors import BadRequestError, NotFoundError


class ClipNotFoundError(NotFoundError):
    error_code = "CLIP_NOT_FOUND"
    default_detail = "Clip not found"


class InvalidClipObjectKeyError(BadRequestError):
    error_code = "INVALID_CLIP_OBJECT_KEY"
    default_detail = "Invalid clip object key"


class ClipObjectNotFoundError(BadRequestError):
    error_code = "CLIP_OBJECT_NOT_FOUND"
    default_detail = "Clip object not found in storage"


class UnsupportedClipContentTypeError(BadRequestError):
    error_code = "UNSUPPORTED_CLIP_CONTENT_TYPE"

    def __init__(self, allowed: list[str]) -> None:
        super().__init__(detail=f"Unsupported clip content type. Allowed: {', '.join(sorted(allowed))}")
