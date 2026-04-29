"""
Root conftest.py.

Inserts the project's src/ directory onto sys.path before any test is
collected so that `import application`, `import domain`, `import config`,
etc. all resolve correctly without requiring an editable install.
"""
import sys
import os

# Resolve <repo-root>/src regardless of where pytest is invoked from.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC  = os.path.join(_HERE, "src")

if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
