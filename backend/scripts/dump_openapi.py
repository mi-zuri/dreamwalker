"""Print the OpenAPI schema without starting a server.

`bun run gen:api` points `openapi-typescript` at a running backend, which is
the convenient thing on a workstation. CI has no backend running and should
not have to orchestrate one just to check that the frontend's types still
match the API, so it goes through here instead.
"""

import json
import sys
from pathlib import Path

# Run as a file, so Python puts scripts/ on the path rather than the project.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

json.dump(app.openapi(), sys.stdout, indent=2)
