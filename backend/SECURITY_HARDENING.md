# Security hardening — Step 0 (deployment notes)

Зміни **не торкаються** бізнес-логіки, шляхів API, схеми БД і legacy-функціональності.
Але вони роблять обов'язковим те, що раніше мало небезпечний default. Перед деплоєм
виконайте кроки нижче, інакше backend не стартує.

## 1. Створити `backend/.env`

```bash
cd backend
cp .env.example .env
```

Заповніть обов'язкові ключі:

| Ключ | Обов'язковий | Було раніше |
|------|--------------|-------------|
| `JWT_SECRET_KEY` | так | публічний placeholder у коді 6 файлів |
| `RH_DB_HOST` | так | значення в коді |
| `RH_DB_USERNAME` | так | значення в коді |
| `RH_DB_PASSWORD` | так | **реальний пароль у коді** |
| `RH_DB_DATABASE` | так | значення в коді |
| `OC_DB_*` | за потреби | вже читалися з env |

## 2. JWT — важливо про існуючі сесії

Формат токена не змінено (HS256, той самий payload).

* Якщо система вже працює і ви хочете **зберегти видані токени** — вкажіть у
  `JWT_SECRET_KEY` той самий секрет, що використовувався раніше.
* Якщо секрет був публічним placeholder-ом — його треба замінити, і тоді всі
  користувачі один раз перелогіняться. Це очікуваний наслідок.

Згенерувати новий секрет:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Поведінка при відсутньому секреті:

* `ENVIRONMENT=production` (значення за замовчуванням) → явна помилка запуску;
* `ENVIRONMENT=development` → тимчасовий випадковий секрет + warning у лог.

## 3. Runtime-міграції (`/api/migrations/*`)

10 endpoints виконували `CREATE`/`ALTER TABLE` у відповідь на анонімний HTTP-запит.
Endpoints **збережені**, шляхи й формати відповідей не змінені, але тепер закриті:

```bash
# у звичайному режимі роботи
ALLOW_RUNTIME_MIGRATIONS=false
```

Щоб застосувати схему під час деплойменту:

```bash
# варіант, що рекомендується — CLI, без HTTP
python apply_all_migrations.py --dry-run
python apply_all_migrations.py

# варіант через HTTP (лише на час деплою)
# .env: ALLOW_RUNTIME_MIGRATIONS=true, MIGRATION_TOKEN=<мін. 16 символів>
curl -X POST https://<host>/api/migrations/<name> \
     -H "X-Migration-Token: $MIGRATION_TOKEN"
# після завершення повернути ALLOW_RUNTIME_MIGRATIONS=false
```

Без вимикача endpoint віддає `503`, з невірним токеном — `403`.

## 4. Sync (`/api/sync/*`)

Контракти не змінені. Змінилося лише виконання:

* захардкоджений шлях до venv → `SYNC_PYTHON_BIN` з fallback на `sys.executable`;
* робоча директорія → `SYNC_BASE_DIR` з fallback на каталог `backend`;
* шлях логу → `SYNC_LOG_PATH`;
* ім'я скрипта фіксоване константою і не приходить із запиту;
* перевірка, що скрипт не виходить за межі базової директорії;
* subprocess отримує список аргументів, shell вимкнений.

Якщо в production використовувався саме venv-інтерпретатор, задайте його явно:

```
SYNC_PYTHON_BIN=/root/.venv/bin/python
```

## 5. `mysqldump` у `apply_all_migrations.py`

Пароль більше не передається в аргументах процесу (був видний у `ps` будь-якому
користувачу системи) — тепер іде через `MYSQL_PWD`. Поведінка бекапу не змінилася.

## 6. Generated files

`.gitignore` доповнено `generated_pdfs/` і `uploads/`.
Уже закомічені файли (3 PDF та `backend/uploads/.gitignore`) **залишені tracked** —
їх видалення з історії потребує окремого рішення.

## 7. Регресійні тести

```bash
cd backend
python tests/test_security_config.py        # 19 перевірок
# або
python -m pytest tests/test_security_config.py -v
```

Тести перевіряють інваріанти безпеки й незмінність API-префіксів,
не потребують ані БД, ані запущеного сервера.