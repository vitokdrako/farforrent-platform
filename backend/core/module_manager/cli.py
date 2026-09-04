"""CLI для керування модулями: основа майбутнього `rentalos modules`.

Використання:
    python -m core.module_manager.cli list
    python -m core.module_manager.cli status finance
    python -m core.module_manager.cli enable finance
    python -m core.module_manager.cli disable analytics
    python -m core.module_manager.cli disable crm --cascade
    python -m core.module_manager.cli permissions
    python -m core.module_manager.cli order
    python -m core.module_manager.cli set core inventory rental
"""
import argparse
import json
import sys
from typing import List, Optional

from . import build_module_manager
from .manager import ModuleManager
from .registry import ModuleError

_ON = "●"
_OFF = "○"


def _print_list(manager: ModuleManager) -> None:
    status = manager.status()
    print("\nRENTAL OS — MODULES")
    print("─" * 62)
    for module in status["modules"]:
        mark = _ON if module["enabled"] else _OFF
        state = "ON " if module["enabled"] else "OFF"
        tag = " [CORE]" if module["core"] else ""
        print(f"  {mark} {module['title']:<26} {state}{tag}")
        if module["requires"]:
            print(f"      requires: {', '.join(module['requires'])}")
    print("─" * 62)
    print(
        f"  Увімкнено: {status['enabled_count']} / {status['total']}    "
        f"Permissions: {len(status['permissions'])}"
    )
    print(f"  Стан: {status['state_file']}")
    for warning in status["warnings"]:
        print(f"  ⚠  {warning}")
    print()


def _print_status(manager: ModuleManager, name: str) -> None:
    print(json.dumps(manager.module_status(name), ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    """Побудувати парсер аргументів CLI."""
    parser = argparse.ArgumentParser(
        prog="rentalos modules",
        description="Керування модулями Rental OS",
    )
    parser.add_argument(
        "--json", action="store_true", help="вивід у форматі JSON"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="показати всі модулі та їх стан")

    p_status = sub.add_parser("status", help="детальний статус модуля")
    p_status.add_argument("name", nargs="?", help="ім'я модуля (без нього — весь стан)")

    p_enable = sub.add_parser("enable", help="увімкнути модуль")
    p_enable.add_argument("name")
    p_enable.add_argument(
        "--no-deps",
        action="store_true",
        help="не вмикати залежності автоматично (помилка, якщо їх немає)",
    )

    p_disable = sub.add_parser("disable", help="вимкнути модуль")
    p_disable.add_argument("name")
    p_disable.add_argument(
        "--cascade",
        action="store_true",
        help="вимкнути також усі залежні модулі",
    )

    sub.add_parser("permissions", help="permissions увімкнених модулів")
    sub.add_parser("order", help="порядок завантаження модулів")

    p_set = sub.add_parser("set", help="встановити повний набір модулів")
    p_set.add_argument("names", nargs="+")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Точка входу CLI.

    Returns:
        Код виходу процесу: 0 — успіх, 1 — помилка модульної системи.
    """
    args = build_parser().parse_args(argv)
    manager = build_module_manager()

    try:
        if args.command == "list":
            if args.json:
                print(json.dumps(manager.status(), ensure_ascii=False, indent=2))
            else:
                _print_list(manager)

        elif args.command == "status":
            if args.name:
                _print_status(manager, args.name)
            else:
                print(json.dumps(manager.status(), ensure_ascii=False, indent=2))

        elif args.command == "enable":
            result = manager.enable_module(
                args.name, with_dependencies=not args.no_deps
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                extra = result.get("also_enabled") or []
                suffix = f" (+ {', '.join(extra)})" if extra else ""
                changed = "увімкнено" if result["changed"] else "уже було увімкнено"
                print(f"{_ON} {args.name}: {changed}{suffix}")

        elif args.command == "disable":
            result = manager.disable_module(args.name, cascade=args.cascade)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                extra = result.get("also_disabled") or []
                suffix = f" (+ {', '.join(extra)})" if extra else ""
                changed = "вимкнено" if result["changed"] else "уже було вимкнено"
                print(f"{_OFF} {args.name}: {changed}{suffix}")

        elif args.command == "permissions":
            permissions = manager.active_permissions()
            if args.json:
                print(json.dumps(permissions, ensure_ascii=False, indent=2))
            else:
                for permission in permissions:
                    print(permission)
                print(f"\nВсього: {len(permissions)}")

        elif args.command == "order":
            order = manager.enabled_modules()
            if args.json:
                print(json.dumps(order, ensure_ascii=False, indent=2))
            else:
                for index, name in enumerate(order, start=1):
                    print(f"{index:>2}. {name}")

        elif args.command == "set":
            result = manager.set_enabled_modules(args.names)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Увімкнено: {', '.join(result['enabled'])}")

    except ModuleError as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())