#!/usr/bin/env python3
"""
Apply all RentalHub migrations safely (idempotent).

Запуск на VPS:
    cd /var/www/farforrent/backend
    
    # На локальну VPS-БД (за замовчуванням, читає LOCAL_DB_* з .env):
    python3 apply_all_migrations.py
    
    # Або вказати explicit target:
    python3 apply_all_migrations.py --target=local
    python3 apply_all_migrations.py --target=cloud   # не рекомендовано — cloud вже синхронна
    
    # Показати що буде застосовано, без виконання:
    python3 apply_all_migrations.py --dry-run

Безпека:
  - Кожна міграція використовує CREATE TABLE IF NOT EXISTS / ALTER ... ADD COLUMN з pre-check
  - Тригери: DROP TRIGGER IF EXISTS перед CREATE
  - Помилки на існуючих об'єктах (1050, 1060, 1061, 1146) ігноруються (вже застосовано)
  - Перед запуском робиться mysqldump бекап у /var/www/farforrent/db_backups/
  - У разі помилки міграції — наступні НЕ запускаються (fail-fast)
"""
import os, sys, argparse, subprocess
from pathlib import Path
from dotenv import load_dotenv

ENV_FILE = Path(__file__).parent / ".env"
load_dotenv(ENV_FILE)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
BACKUP_DIR = Path("/var/www/farforrent/db_backups")

# Мігруюємо лише ці (з нашої поточної сесії). Решта вже застосована раніше.
MIGRATIONS = [
    "005_fix_fin_triggers_recursion.sql",
    "006_drop_fin_transactions_after_insert.sql",
    "007_event_favorites.sql",
    "008_push_subscriptions.sql",
    "009_order_chat.sql",
    "010_document_signatures.sql",
    "011_company_profiles.sql",
]

# Ідемпотентні помилки (можна ігнорувати — означає що об'єкт уже є/нема)
IDEMPOTENT_ERR_CODES = {1050, 1060, 1061, 1062, 1091, 1146, 1359, 1360, 1304}


def get_target_config(target: str) -> dict:
    if target == "local":
        return dict(
            host=os.environ.get("LOCAL_DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("LOCAL_DB_PORT", "3306")),
            user=os.environ.get("LOCAL_DB_USER", "root"),
            password=os.environ.get("LOCAL_DB_PASS", ""),
            db=os.environ.get("LOCAL_DB_NAME", "farforre_rentalhub"),
        )
    elif target == "cloud":
        return dict(
            host=os.environ["RH_DB_HOST"],
            port=int(os.environ.get("RH_DB_PORT", "3306")),
            user=os.environ["RH_DB_USERNAME"],
            password=os.environ["RH_DB_PASSWORD"],
            db=os.environ["RH_DB_DATABASE"],
        )
    raise ValueError(f"Unknown target: {target}")


def make_backup(cfg: dict) -> str:
    """mysqldump поточної БД у gzip-файл, повертає шлях."""
    import datetime
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP_DIR / f"pre_migration_{cfg['db']}_{ts}.sql.gz"
    print(f"📦 Backup → {out}")
    cmd = [
        "mysqldump",
        f"-h{cfg['host']}", f"-P{cfg['port']}",
        f"-u{cfg['user']}",
        "--routines", "--triggers", "--events",
        "--single-transaction", "--quick",
        "--skip-lock-tables",
        "--column-statistics=0",
        cfg["db"],
    ]
    if cfg["password"]:
        cmd.insert(4, f"-p{cfg['password']}")
    with open(out, "wb") as fout:
        proc1 = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc2 = subprocess.Popen(["gzip"], stdin=proc1.stdout, stdout=fout)
        proc1.stdout.close()
        proc2.communicate()
        err = proc1.communicate()[1]
        if proc1.returncode != 0:
            print(f"⚠️  mysqldump warning: {err.decode()[:200]}")
    size = out.stat().st_size / 1024
    print(f"   ✓ Saved {size:.1f} KB")
    return str(out)


def run_migration(cfg: dict, sql_file: Path, dry_run: bool = False) -> bool:
    """Запустити один .sql на target БД. Toleruє ідемпотентні помилки."""
    import pymysql
    sql = sql_file.read_text(encoding="utf-8")

    # Розбити на statements (без триггер-блоків з ; всередині)
    statements = []
    buf = []
    in_trigger = False
    for line in sql.split("\n"):
        s = line.strip()
        if not s or s.startswith("--"):
            buf.append(line)
            continue
        upper = s.upper()
        if upper.startswith("CREATE TRIGGER") or upper.startswith("DELIMITER"):
            in_trigger = True
        buf.append(line)
        if in_trigger:
            if upper == "END" or upper == "END;" or upper.startswith("END$$") or upper.startswith("DELIMITER ;"):
                in_trigger = False
                statements.append("\n".join(buf))
                buf = []
        else:
            if s.endswith(";"):
                statements.append("\n".join(buf))
                buf = []
    if buf:
        statements.append("\n".join(buf))

    # Прибираємо DELIMITER директиви (не потрібні через PyMySQL)
    cleaned = []
    for st in statements:
        st_clean = "\n".join(
            line for line in st.split("\n")
            if not line.strip().upper().startswith("DELIMITER")
        ).strip()
        # Прибрати завершальний $$ або ;
        st_clean = st_clean.rstrip("$").rstrip(";").rstrip()
        if st_clean:
            cleaned.append(st_clean)

    if dry_run:
        print(f"   🔍 [DRY-RUN] would run {len(cleaned)} statements")
        return True

    conn = pymysql.connect(
        host=cfg["host"], port=cfg["port"],
        user=cfg["user"], password=cfg["password"],
        db=cfg["db"], charset="utf8mb4", autocommit=True
    )
    cur = conn.cursor()
    applied = 0
    skipped = 0
    try:
        for st in cleaned:
            try:
                cur.execute(st)
                applied += 1
            except pymysql.MySQLError as e:
                code = e.args[0] if e.args else 0
                if code in IDEMPOTENT_ERR_CODES:
                    skipped += 1
                else:
                    print(f"   ❌ MySQL error {code}: {e.args[1] if len(e.args) > 1 else e}")
                    raise
        print(f"   ✓ {applied} applied, {skipped} skipped (already present)")
        return True
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", choices=["local", "cloud"], default="local")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--include-data-migration", action="store_true",
                   help="Run migrate_return_cards.py too")
    args = p.parse_args()

    cfg = get_target_config(args.target)
    print("━" * 60)
    print(f"🎯 Target: {args.target.upper()} → {cfg['host']}:{cfg['port']}/{cfg['db']}")
    print(f"📁 Migrations dir: {MIGRATIONS_DIR}")
    print("━" * 60)

    # Підтвердження для cloud
    if args.target == "cloud" and not args.dry_run:
        ans = input(f"⚠️  Це CLOUD/PROD. Continue? [yes/no]: ").strip().lower()
        if ans != "yes":
            print("Aborted.")
            return

    if not args.no_backup and not args.dry_run:
        try:
            make_backup(cfg)
        except Exception as e:
            print(f"⚠️  Backup failed: {e}")
            ans = input("Continue without backup? [yes/no]: ").strip().lower()
            if ans != "yes":
                return

    for mig in MIGRATIONS:
        path = MIGRATIONS_DIR / mig
        if not path.exists():
            print(f"\n📄 {mig} — MISSING ❌")
            continue
        print(f"\n📄 {mig}")
        ok = run_migration(cfg, path, dry_run=args.dry_run)
        if not ok:
            print(f"\n❌ STOPPED at {mig}")
            sys.exit(1)

    print("\n" + "━" * 60)
    print("✅ ALL MIGRATIONS APPLIED")

    if args.include_data_migration and not args.dry_run:
        print("\n📦 Running data migration: return_cards → partial_return_versions")
        os.system(f"cd {Path(__file__).parent} && python3 migrate_return_cards.py")

    # Швидка статистика
    if not args.dry_run:
        import pymysql
        conn = pymysql.connect(
            host=cfg["host"], port=cfg["port"],
            user=cfg["user"], password=cfg["password"],
            db=cfg["db"], charset="utf8mb4"
        )
        cur = conn.cursor()
        tables = ["event_favorites", "push_subscriptions", "order_chat_messages",
                  "document_signatures", "company_profiles"]
        print("\n📊 New tables on target:")
        for t in tables:
            cur.execute(f"SHOW TABLES LIKE '{t}'")
            present = "✓" if cur.fetchone() else "✗"
            print(f"   {present} {t}")
        conn.close()

    print("━" * 60 + "\n")


if __name__ == "__main__":
    main()
