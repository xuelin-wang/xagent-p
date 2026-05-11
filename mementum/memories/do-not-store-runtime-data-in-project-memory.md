# Do Not Store Runtime Data in Project Memory

Symbol: ⚠️

`mementum/` is for engineering/project context only.

Do not store runtime application records, raw logs, user data, customer data, production data, secrets, credentials, or large generated artifacts here.

Why it matters:
- Project memory is committed to Git.
- Git history is durable and hard to fully erase.
- Runtime data often has privacy, retention, and access-control requirements.

Future implication:
- If data belongs to the running application, store it in the appropriate runtime datastore, not in `mementum/`.
