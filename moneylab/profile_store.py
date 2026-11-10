"""Storage boundary: local development only, never a shared anonymous profile.

An authenticated hosted adapter must derive its owner from verified identity,
not from a form, URL or this development adapter. See docs/product-overhaul.md.
"""
from pathlib import Path
from typing import Protocol
from contextlib import contextmanager
import os
import sqlite3

from moneylab.plan_setup import EXPENSES, PRIORITIES
from moneylab.workspace import workspace_from_json_full, workspace_to_json
from moneylab.action_plan import validate_preference
from moneylab.progress import validate_tracking
import json

UNKNOWN_FIELDS = {"income", *EXPENSES, "checking", "savings", "debts"}


def validate_metadata(metadata):
    if not isinstance(metadata, dict) or not {"priority", "unknown"}.issubset(metadata) or set(metadata) - {"priority", "unknown", "is_example", "action_preference", "accepted_plan"}:
        raise ValueError("Unsupported planning details.")
    if metadata["priority"] not in PRIORITIES:
        raise ValueError("Unknown financial priority.")
    unknown = metadata["unknown"]
    if not isinstance(unknown, list) or any(not isinstance(v, str) or v not in UNKNOWN_FIELDS for v in unknown):
        raise ValueError("Unsupported missing financial details.")
    if not isinstance(metadata.get("is_example", False), bool):
        raise ValueError("Invalid example marker.")
    result = {"priority": metadata["priority"], "unknown": list(dict.fromkeys(unknown)), "is_example": metadata.get("is_example", False)}
    # Old v4 metadata stays byte-shape compatible until these features are used.
    if "action_preference" in metadata:
        result["action_preference"] = validate_preference(metadata["action_preference"])
    if "accepted_plan" in metadata:
        result["accepted_plan"] = validate_tracking(metadata["accepted_plan"])
    return result


def plan_to_json(blocks, scenarios, drafts, metadata):
    return json.dumps({"schema_version": 5,
                       "workspace": json.loads(workspace_to_json(blocks, scenarios, drafts)),
                       "plan": validate_metadata(metadata)}, indent=2)


def _read_workspace(text):
    try:
        return workspace_from_json_full(text)
    except (TypeError, KeyError, ArithmeticError, RecursionError):
        raise ValueError("Workspace contains invalid financial details.") from None


def plan_from_json(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > 200_000:
        raise ValueError("Workspace exceeds the 200 KB limit.")
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        raise ValueError("File is not valid JSON.") from None
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int:
        raise ValueError("Workspace needs a supported integer version.")
    if isinstance(payload, dict) and payload.get("schema_version") in (4, 5):
        if set(payload) != {"schema_version", "workspace", "plan"}:
            raise ValueError("Unexpected workspace fields.")
        metadata = validate_metadata(payload["plan"])
        return (*_read_workspace(json.dumps(payload["workspace"])), metadata)
    return (*_read_workspace(text), {"priority": "Understand my money", "unknown": ["debts"]})


class ProfileStore(Protocol):
    def load(self) -> tuple[str | None, int]: ...
    def save(self, payload: str, expected_revision: int) -> int: ...
    def delete(self, expected_revision: int) -> None: ...


class LocalProfileStore:
    """Explicit single-user development store, with optimistic concurrency.

    A generation counter survives deletion, preventing a stale browser session
    from resurrecting a deleted plan. Values never enter logs or filenames.
    The private file is plaintext; host disk encryption is the owner's choice.
    """
    def __init__(self, directory):
        folder = Path(directory)
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        if folder.is_symlink() or folder.stat().st_uid != os.getuid():
            raise ValueError("Local storage must be an owned private directory.")
        folder.chmod(0o700)
        self.path = folder / "plan.sqlite3"
        if self.path.is_symlink():
            raise ValueError("Local storage cannot use a symbolic link.")
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        self.path.chmod(0o600)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS plan (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT, revision INTEGER NOT NULL)")
            db.execute("INSERT OR IGNORE INTO plan VALUES (1, NULL, 0)")

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA secure_delete=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def load(self):
        with self._connect() as db:
            payload, revision = db.execute("SELECT payload, revision FROM plan WHERE id=1").fetchone()
        if payload is not None:
            plan_from_json(payload)
        return payload, revision

    def save(self, payload, expected_revision):
        plan_from_json(payload)
        with self._connect() as db:
            changed = db.execute("UPDATE plan SET payload=?, revision=revision+1 WHERE id=1 AND revision=?",
                                 (payload, expected_revision)).rowcount
            if changed != 1:
                raise ValueError("Another session changed or deleted this plan. Reload before saving.")
        return expected_revision + 1

    def delete(self, expected_revision):
        with self._connect() as db:
            changed = db.execute("UPDATE plan SET payload=NULL, revision=revision+1 WHERE id=1 AND revision=?",
                                 (expected_revision,)).rowcount
            if changed != 1:
                raise ValueError("Another session changed this plan. Reload before deleting.")


def configured_local_store(address):
    """Fail closed on shared hosts, including Streamlit Community Cloud."""
    directory = os.environ.get("MONEYLAB_LOCAL_STORE")
    if not directory:
        return None
    if address not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("Local saving requires a loopback-only server address. Shared deployments need authenticated storage.")
    return LocalProfileStore(directory)
