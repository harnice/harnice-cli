import os
import sys

# Running this file by path puts its own folder on sys.path. The package
# root is src/, one level up, and the shell stays in the revision folder.
_src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src not in sys.path:
    sys.path.insert(0, _src)

from harnice.cli import main

if __name__ == "__main__":
    main()
