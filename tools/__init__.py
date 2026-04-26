"""Tool exports for the RealtimeAgent.

Any module-level ``FunctionTool`` instances defined in Python files under
the ``tools/`` package are automatically discovered and exposed via
``ALL_TOOLS``.  Just drop a new file with a ``@function_tool``-decorated
function and it will be picked up — no manual registration needed.

Usage:
    from tools import ALL_TOOLS
"""

import importlib
import pkgutil

from agents.tool import FunctionTool

ALL_TOOLS: list[FunctionTool] = []

# Walk every module in this package and collect FunctionTool instances.
for _info in pkgutil.iter_modules(__path__, prefix=__name__ + "."):
    _mod = importlib.import_module(_info.name)
    for _attr in dir(_mod):
        _obj = getattr(_mod, _attr)
        if isinstance(_obj, FunctionTool):
            ALL_TOOLS.append(_obj)
