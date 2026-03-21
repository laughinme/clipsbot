from enum import Enum


class Provider(Enum):
    """Supported authentication providers."""

    EMAIL = "email"
    PHONE_OTP = "phone_otp"
    
    # To be added
    # GOOGLE = "google"
    # APPLE = "apple"
