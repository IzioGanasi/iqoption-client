from enum import Enum


class OptionType(str, Enum):
    BINARY = "binary"
    TURBO = "turbo"
    BLITZ = "blitz"
    DIGITAL = "digital"


class Direction(str, Enum):
    CALL = "call"
    PUT = "put"


class OptionResult(str, Enum):
    OPENED = "opened"
    WIN = "win"
    LOOSE = "loose"
    TIE = "tie"


class AccountType(str, Enum):
    REAL = "real"
    DEMO = "demo"


class InstrumentType(str, Enum):
    BINARY_OPTION = "binary-option"
    TURBO_OPTION = "turbo-option"
    BLITZ_OPTION = "blitz-option"
    DIGITAL_OPTION = "digital-option"
    FX_OPTION = "fx-option"
    MARGINAL_FOREX = "marginal-forex"
    MARGINAL_CFD = "marginal-cfd"
    MARGINAL_CRYPTO = "marginal-crypto"


# Maps OptionType to option_type_id used in binary-options.open-option
OPTION_TYPE_IDS = {
    OptionType.BINARY: 1,
    OptionType.TURBO: 3,
    OptionType.BLITZ: 12,
}

# Maps OptionType to instrument_type string used in subscriptions
INSTRUMENT_TYPE_MAP = {
    OptionType.BINARY: InstrumentType.BINARY_OPTION,
    OptionType.TURBO: InstrumentType.TURBO_OPTION,
    OptionType.BLITZ: InstrumentType.BLITZ_OPTION,
    OptionType.DIGITAL: InstrumentType.DIGITAL_OPTION,
}
