from framework.config import settings

if settings.MODE_DEBUG:
    from devtools import debug as _debug

    def debug(*args, **kwargs):
        return _debug(*args, **kwargs)


else:

    def debug(*_args, **_kwargs):
        pass
