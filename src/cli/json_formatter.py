import json
from dataclasses import is_dataclass, fields
from typing import Any, Optional
from enum import Enum


def _dataclass_tree_to_dict(obj: Any) -> Any:
    """
    Recursively convert a dataclass object (including nested dataclasses)
    into dictionaries and lists, which can be serialized to JSON.
    
    Enhancements:
    - Enum objects are converted to their .value
    - float values are rounded to 4 decimal places
    """
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


def to_json(obj: Any, indent: Optional[int] = 2, compact: bool = False) -> str:
    """
    Convert obj to a JSON string with:
    - Enum serialized as their value
    - Floats rounded to 4 decimal places
    """
    tree_dict = _dataclass_tree_to_dict(obj)

    if compact:
        return json.dumps(tree_dict, separators=(",", ":"), ensure_ascii=False)

    return json.dumps(tree_dict, indent=indent, ensure_ascii=False)
