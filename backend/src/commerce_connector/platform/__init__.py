__all__ = ["CommercePlatformService", "PlatformSettings"]


def __getattr__(name):
    if name == "CommercePlatformService":
        from .service import CommercePlatformService
        return CommercePlatformService
    if name == "PlatformSettings":
        from .settings import PlatformSettings
        return PlatformSettings
    raise AttributeError(name)
