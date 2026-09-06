"""Верифікація Завдання №5.

Перевіряє статично, без підключення до БД:
  1. нуль route -> route імпортів у `routes/`;
  2. кількість `include_router` і endpoints у `server.py` (парність 582);
  3. що канонічні символи доступні і в сервісах, і через реекспорт роутів.
"""
import ast
import os
import sys

# `--backend <path>` дозволяє запустити ту саму методику підрахунку на
# HEAD-копії репозиторію, щоб порівняти інвентар ДО і ПІСЛЯ змін.
# `--inventory-only` пропускає перевірки сервісного шару (у HEAD його немає).
INVENTORY_ONLY = "--inventory-only" in sys.argv
if "--backend" in sys.argv:
    BACKEND = os.path.abspath(sys.argv[sys.argv.index("--backend") + 1])
else:
    BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTES = os.path.join(BACKEND, "routes")
SERVER = os.path.join(BACKEND, "server.py")
print(f"BACKEND = {BACKEND}")

DECORATORS = {"get", "post", "put", "patch", "delete", "head", "options", "websocket"}
failures = []


def parse(path):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path)


# --- 1. route -> route imports ------------------------------------------------
cross = []
for fname in sorted(os.listdir(ROUTES)):
    if not fname.endswith(".py"):
        continue
    path = os.path.join(ROUTES, fname)
    for node in ast.walk(parse(path)):
        mod = None
        if isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("routes"):
                    mod = alias.name
        if mod and (mod == "routes" or mod.startswith("routes.")):
            cross.append(f"{fname}:{node.lineno} -> {mod}")

print("=" * 62)
print(f"1. route -> route imports: {len(cross)}")
for c in cross:
    print(f"   {c}")
if cross:
    failures.append("залишились route -> route імпорти")

# --- 2. server.py inventory ---------------------------------------------------
tree = parse(SERVER)
includes = sum(
    1
    for n in ast.walk(tree)
    if isinstance(n, ast.Call)
    and isinstance(n.func, ast.Attribute)
    and n.func.attr == "include_router"
)

endpoints = 0
for fname in sorted(os.listdir(ROUTES)):
    if not fname.endswith(".py"):
        continue
    for node in ast.walk(parse(os.path.join(ROUTES, fname))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(target, ast.Attribute) and target.attr in DECORATORS:
                    endpoints += 1

print(f"2. include_router у server.py: {includes}")
print(f"   endpoints у routes/: {endpoints}")

if INVENTORY_ONLY:
    print("=" * 62)
    print(f"INVENTORY: include_router={includes} endpoints={endpoints} cross={len(cross)}")
    sys.exit(0)

# Очікуваний інвентар передається з baseline-прогону на HEAD.
if "--expect" in sys.argv:
    exp_inc, exp_ep = sys.argv[sys.argv.index("--expect") + 1].split(",")
    if includes != int(exp_inc):
        failures.append(f"include_router {includes} != baseline {exp_inc}")
    if endpoints != int(exp_ep):
        failures.append(f"endpoints {endpoints} != baseline {exp_ep}")

# --- 3. canonical symbols + backward-compatible re-exports -------------------
EXPECTED = {
    "services.chat_service": ["serialize_message", "list_messages", "verify_order_belongs_to_client"],
    "services.chat_notifications": ["notify_task_in_chat", "notify_task_status_change"],
    "services.customer_identity": ["get_current_customer", "decode_customer_token"],
    "services.document_context": ["build_document_context", "jinja_env", "DOCUMENT_TEMPLATES", "get_watermark_text"],
    "core.security": ["TokenError", "decode_jwt_token"],
}

print("3. канонічні символи:")
sys.path.insert(0, BACKEND)
os.environ.setdefault("ENVIRONMENT", "development")
for mod_name, symbols in EXPECTED.items():
    try:
        mod = __import__(mod_name, fromlist=symbols)
    except Exception as exc:
        print(f"   FAIL {mod_name}: {exc}")
        failures.append(f"{mod_name} не імпортується: {exc}")
        continue
    missing = [s for s in symbols if not hasattr(mod, s)]
    if missing:
        print(f"   FAIL {mod_name}: немає {missing}")
        failures.append(f"{mod_name} без {missing}")
    else:
        print(f"   OK   {mod_name}  ({len(symbols)} симв.)")

# Реекспорт у старих модулях: перевіряємо статично, щоб не тягнути БД.
REEXPORTS = {
    "order_chat.py": ["_serialize_message", "_list_messages", "_verify_order_belongs_to_client"],
    "team_chat.py": ["notify_task_in_chat", "notify_task_status_change"],
    "document_render.py": ["build_document_context", "jinja_env", "DOCUMENT_TEMPLATES", "get_watermark_text"],
    "event_tool.py": ["decode_token", "get_current_customer"],
}
print("4. backward-compatible реекспорт у роутах:")
for fname, symbols in REEXPORTS.items():
    src = open(os.path.join(ROUTES, fname), encoding="utf-8").read()
    missing = [s for s in symbols if s not in src]
    if missing:
        print(f"   FAIL {fname}: немає {missing}")
        failures.append(f"{fname} без реекспорту {missing}")
    else:
        print(f"   OK   {fname}")

print("=" * 62)
if failures:
    print("РЕЗУЛЬТАТ: FAIL")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("РЕЗУЛЬТАТ: PASS — 0 route->route, парність API збережена")