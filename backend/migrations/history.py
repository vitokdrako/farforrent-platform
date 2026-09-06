#!/usr/bin/env python3
"""Migration history table and the database contract the runner depends on.

Two things live here:

* :class:`HistoryRecord` / :data:`HISTORY_TABLE_DDL` — what gets written down
  about every migration, including the ones that were deliberately *not* run;
* :class:`Backend` — the narrow interface the runner uses. The runner never
  touches pymysql directly, so its decision logic can be tested against an
  in-memory backend without a MySQL server and without production credentials.

``status`` is the field that keeps the history honest. ``applied`` means the SQL
really executed; ``stamped`` means an existing schema was adopted without
running DDL; ``skipped`` means the migration is known to be inapplicable. They
are never collapsed into a single boolean.
"""

from __future__ import annotations

import getpass
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

RUNNER_VERSION = "1.0"

HISTORY_TABLE = "schema_migrations"

# `version` is the primary key: re-applying a migration becomes physically
# impossible rather than merely discouraged. VARCHAR(64) (not 32) because the
# unnumbered legacy files are addressed by their full stem, e.g.
# `create_product_damage_history`.
HISTORY_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS `{HISTORY_TABLE}` (
  `version`             VARCHAR(64)  NOT NULL,
  `name`                VARCHAR(255) NOT NULL,
  `checksum`            CHAR(64)     NOT NULL,
  `status`              VARCHAR(16)  NOT NULL,
  `applied_at`          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `applied_by`          VARCHAR(128) NOT NULL,
  `runner_version`      VARCHAR(32)  NOT NULL,
  `execution_ms`        INT UNSIGNED NULL,
  `statements_executed` INT UNSIGNED NOT NULL DEFAULT 0,
  `schema_fingerprint`  CHAR(64)     NULL,
  `notes`               TEXT         NULL,
  `error_message`       TEXT         NULL,
  PRIMARY KEY (`version`),
  KEY `idx_schema_migrations_applied_at` (`applied_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
""".strip()

_HISTORY_COLUMNS = (
    "version",
    "name",
    "checksum",
    "status",
    "applied_at",
    "applied_by",
    "runner_version",
    "execution_ms",
    "statements_executed",
    "schema_fingerprint",
    "notes",
    "error_message",
)


class MigrationStatus(str, Enum):
    """What actually happened to a migration."""

    #: The SQL was executed against this database by the runner.
    APPLIED = "applied"
    #: The objects were already present; adopted without executing DDL.
    STAMPED = "stamped"
    #: Known inapplicable (see ``catalog.SKIP_RULES``); no SQL executed, ever.
    SKIPPED = "skipped"
    #: Execution started and failed. Kept on purpose so the reason survives.
    FAILED = "failed"


#: Statuses that block a migration from being attempted again by ``upgrade``.
SETTLED_STATUSES = (
    MigrationStatus.APPLIED,
    MigrationStatus.STAMPED,
    MigrationStatus.SKIPPED,
)


@dataclass(frozen=True)
class HistoryRecord:
    """One row of :data:`HISTORY_TABLE`."""

    version: str
    name: str
    checksum: str
    status: MigrationStatus
    applied_by: str
    runner_version: str = RUNNER_VERSION
    execution_ms: int | None = None
    statements_executed: int = 0
    schema_fingerprint: str | None = None
    notes: str | None = None
    error_message: str | None = None
    applied_at: datetime | None = None

    @property
    def is_settled(self) -> bool:
        return self.status in SETTLED_STATUSES

    def as_row(self) -> dict[str, object]:
        return {
            "version": self.version,
            "name": self.name,
            "checksum": self.checksum,
            "status": self.status.value,
            "applied_at": self.applied_at or datetime.now(),
            "applied_by": self.applied_by,
            "runner_version": self.runner_version,
            "execution_ms": self.execution_ms,
            "statements_executed": self.statements_executed,
            "schema_fingerprint": self.schema_fingerprint,
            "notes": self.notes,
            "error_message": self.error_message,
        }


def current_actor() -> str:
    """Who is running the migration, for the audit trail."""
    for env_var in ("MIGRATION_ACTOR", "CI_JOB_NAME", "USER", "USERNAME"):
        value = os.environ.get(env_var)
        if value:
            return value[:128]
    try:
        return getpass.getuser()[:128]
    except Exception:  # pragma: no cover - depends on host account setup
        return "unknown"


class Backend(Protocol):
    """The database operations the runner is allowed to perform."""

    @property
    def label(self) -> str:
        """Human-readable target description for logs (never a password)."""

    def tables(self) -> set[str]:
        ...

    def views(self) -> set[str]:
        ...

    def triggers(self) -> set[str]:
        ...

    def execute(self, statement: str) -> None:
        """Execute a single SQL statement."""

    def history_exists(self) -> bool:
        ...

    def history_create(self) -> None:
        ...

    def history_rows(self) -> list[HistoryRecord]:
        ...

    def history_insert(self, record: HistoryRecord) -> None:
        ...

    def close(self) -> None:
        ...


class DatabaseConfigError(RuntimeError):
    """Raised when the target database is not fully configured."""


@dataclass(frozen=True)
class DatabaseConfig:
    """Connection settings for the migration target.

    ``MIGRATION_DB_*`` is read first so a staging target can be pointed at
    without touching the application's own ``RH_DB_*`` variables. Passwords are
    never rendered by :meth:`label`.
    """

    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def label(self) -> str:
        return f"{self.host}:{self.port}/{self.database}"

    @property
    def is_local(self) -> bool:
        return self.host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    @classmethod
    def from_env(cls) -> DatabaseConfig:
        def pick(*names: str, default: str | None = None) -> str:
            for name in names:
                value = os.environ.get(name)
                if value:
                    return value
            if default is not None:
                return default
            raise DatabaseConfigError(
                "Missing migration target configuration: set "
                + " or ".join(names)
                + ". See backend/.env.example."
            )

        return cls(
            host=pick("MIGRATION_DB_HOST", "RH_DB_HOST"),
            port=int(pick("MIGRATION_DB_PORT", "RH_DB_PORT", default="3306")),
            user=pick("MIGRATION_DB_USER", "RH_DB_USERNAME"),
            password=pick("MIGRATION_DB_PASSWORD", "RH_DB_PASSWORD", default=""),
            database=pick("MIGRATION_DB_NAME", "RH_DB_DATABASE"),
        )


class MySQLBackend:
    """:class:`Backend` implementation on top of pymysql."""

    def __init__(self, config: DatabaseConfig):
        import pymysql  # imported lazily so tests never need the driver

        self._config = config
        self._conn = pymysql.connect(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            database=config.database,
            charset="utf8mb4",
            # DDL in MySQL commits implicitly; an explicit transaction would
            # only create the illusion of an atomic migration.
            autocommit=True,
        )

    @property
    def label(self) -> str:
        return self._config.label

    def _scalars(self, sql: str, params: tuple = ()) -> set[str]:
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return {row[0] for row in cur.fetchall()}

    def tables(self) -> set[str]:
        return self._scalars(
            "SELECT LOWER(TABLE_NAME) FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE'"
        )

    def views(self) -> set[str]:
        return self._scalars(
            "SELECT LOWER(TABLE_NAME) FROM information_schema.VIEWS "
            "WHERE TABLE_SCHEMA = DATABASE()"
        )

    def triggers(self) -> set[str]:
        return self._scalars(
            "SELECT LOWER(TRIGGER_NAME) FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA = DATABASE()"
        )

    def execute(self, statement: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(statement)

    def history_exists(self) -> bool:
        return HISTORY_TABLE in self.tables()

    def history_create(self) -> None:
        self.execute(HISTORY_TABLE_DDL)

    def history_rows(self) -> list[HistoryRecord]:
        columns = ", ".join(f"`{name}`" for name in _HISTORY_COLUMNS)
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT {columns} FROM `{HISTORY_TABLE}` "
                "ORDER BY `applied_at`, `version`"
            )
            rows = cur.fetchall()
        return [self._to_record(dict(zip(_HISTORY_COLUMNS, row))) for row in rows]

    @staticmethod
    def _to_record(row: dict) -> HistoryRecord:
        return HistoryRecord(
            version=row["version"],
            name=row["name"],
            checksum=row["checksum"],
            status=MigrationStatus(row["status"]),
            applied_by=row["applied_by"],
            runner_version=row["runner_version"],
            execution_ms=row["execution_ms"],
            statements_executed=row["statements_executed"] or 0,
            schema_fingerprint=row["schema_fingerprint"],
            notes=row["notes"],
            error_message=row["error_message"],
            applied_at=row["applied_at"],
        )

    def history_insert(self, record: HistoryRecord) -> None:
        row = record.as_row()
        columns = ", ".join(f"`{name}`" for name in _HISTORY_COLUMNS)
        placeholders = ", ".join(["%s"] * len(_HISTORY_COLUMNS))
        with self._conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO `{HISTORY_TABLE}` ({columns}) VALUES ({placeholders})",
                tuple(row[name] for name in _HISTORY_COLUMNS),
            )

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:  # pragma: no cover - closing a dead socket
            pass