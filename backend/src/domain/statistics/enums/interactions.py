from enum import Enum


class Interaction(Enum):
    """Book interaction types"""
    CLICK = "click"
    LIKE = "like"
    RESERVE = "reserve"
