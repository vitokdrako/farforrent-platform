"""Versioned schema migrations for the RentalHub database.

Entry points:
    python -m migrations.runner status
    python -m migrations.runner install     # empty database only
    python -m migrations.runner stamp --to 011
    python -m migrations.runner upgrade

Design notes: ``migrations/MIGRATION_VERSIONING.md``.
Staging checklist: ``migrations/STAGING_VERIFICATION.md``.
"""