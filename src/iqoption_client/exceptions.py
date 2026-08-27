class IQOptionError(Exception):
    pass

class AuthenticationError(IQOptionError):
    pass

class WebSocketError(IQOptionError):
    pass

class TradingError(IQOptionError):
    pass

class TimeoutError(IQOptionError):
    pass

class AssetError(IQOptionError):
    pass
