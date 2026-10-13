# AUBIE IT Token Tools

Controlled shell access for AUBIEETERNAL IT support.

## Files

- `aubie_orchestrator.py` — Issues short-lived tokens and runs approved commands. Main entry point for AUBIE.
- `issue_token.py` — Interactive helper that prints a ready-to-paste Open WebUI message.

## Setup

1. Set the same long random `SECRET` in:
   - These scripts
   - The Open WebUI `aubie_it_tool`
2. Keep the real secret only on the local machine. Do not commit it.

## Usage

```bash
python3 aubie_orchestrator.py "df -h"
python3 aubie_orchestrator.py "free -h"
```

Or from other Python code:

```python
from aubie_orchestrator import run_with_token
result = run_with_token("df -h && free -h")
print(result["stdout"])
```

Tokens expire quickly and only allow the commands listed when they are issued. AUBIE remains the authority that grants access.
