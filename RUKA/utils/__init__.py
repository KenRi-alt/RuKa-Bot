import importlib

_MODULES = {
    "userLevel": ".user_level",
    "admin": ".admin",
    "botAdmin": ".bot_admin",
    "privateOnly": ".private_only",
    "groupOnly": ".group_only",
    "BlockList": ".block_list",
    "ignoreDisabled": ".disable",
    "chatAction": ".chat_action",
    "loggerChat": ".logger_chat",
}

__all__ = list(_MODULES.keys())


def __getattr__(name: str):
    if name in _MODULES:
        mod = importlib.import_module(_MODULES[name], __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")