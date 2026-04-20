import json
from dataclasses import is_dataclass, fields
from typing import Any, Optional
from enum import Enum


def _dataclass_tree_to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        result = {}
        for f in fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = _dataclass_tree_to_dict(value)
        return result

    elif isinstance(obj, (list, tuple)):
        return [_dataclass_tree_to_dict(item) for item in obj]

    elif isinstance(obj, dict):
        return {k: _dataclass_tree_to_dict(v) for k, v in obj.items()}

    elif isinstance(obj, Enum):
        return obj.value

    elif isinstance(obj, float):
        return round(obj, 4)

    else:
        return obj


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, complex):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def to_json(obj: Any, indent: Optional[int] = 2, compact: bool = False) -> str:
    tree_dict = _dataclass_tree_to_dict(obj)
    if compact:
        return json.dumps(tree_dict, separators=(",", ":"), ensure_ascii=False, default=json_serial)
    return json.dumps(tree_dict, indent=indent, ensure_ascii=False, default=json_serial)
