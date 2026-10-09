"""
Damage Pricing Rules - Тарифи на відшкодування пошкоджень
© FarforDecorOrenda 2025
Source: https://www.farforrent.com.ua/opis-zbitkiv
"""

DAMAGE_CATEGORIES = [
    {
        "id": "furniture",
        "name": "Меблі",
        "damages": [
            {"type": "dirty_upholstery", "name": "Брудна оббивка / сидіння / каркас", "min": 1000},
            {"type": "chips_scratches", "name": "Скол, подряпини, тріщини, втрата деталей", "min": 800, "max": "full"},
            {"type": "burn_hole", "name": "Пропал або дірка", "min": 5000},
            {"type": "dirty_legs", "name": "Ніжки брудні в землі/глині/піску", "min": 800},
            {"type": "liquid_spill", "name": "Залито рідиною (вода, вино, сік)", "min": 1000, "max": 2500},
            {"type": "wet", "name": "Мокрі або вологі", "min": 1000, "max": 2000},
            {"type": "no_cover", "name": "Немає фірмового чохла", "fixed": 1400},
            {"type": "no_stretch", "name": "Немає пакування в стрейч", "min": 500, "max": 1000},
        ]
    },
    {
        "id": "tables",
        "name": "Столики",
        "damages": [
            {"type": "dirty", "name": "Брудні", "min": 500},
            {"type": "chips_scratches", "name": "Сколи або подряпини", "min": 1600, "max": 3000},
            {"type": "damaged_top", "name": "Відсутня або пошкоджена столешня", "min": 1500},
            {"type": "no_stretch", "name": "Без стрейчування", "percent": 30},
            {"type": "no_packaging", "name": "Без власного пакування", "percent": 50},
        ]
    },
    {
        "id": "chairs",
        "name": "Стільці",
        "damages": [
            {"type": "dirty", "name": "Брудні", "min": 700},
            {"type": "chips_scratches", "name": "Сколи або подряпини", "fixed": 1500},
            {"type": "no_stretch", "name": "Без стрейчування", "fixed": 1000},
            {"type": "wet", "name": "Мокрі або вологі", "fixed": 1000},
            {"type": "broken", "name": "Зламані", "full": True},
        ]
    },
    {
        "id": "poufs_textile_chairs",
        "name": "Пуфи та стільці з текстилем",
        "damages": [
            {"type": "dirty_upholstery", "name": "Брудна оббивка або сидіння", "min": 1200, "max": 2000},
            {"type": "damaged_frame", "name": "Пошкоджений каркас", "min": 700},
            {"type": "dirty_legs", "name": "Ніжки брудні в землі/глині/піску", "min": 800},
            {"type": "burn_hole", "name": "Пропал або дірка", "full": True},
            {"type": "liquid_spill", "name": "Залито рідиною", "min": 1200, "max": 2000},
            {"type": "wet", "name": "Мокрі або вологі", "min": 1000, "max": 2000},
            {"type": "no_cover", "name": "Немає фірмового чохла", "fixed": 3000},
            {"type": "no_stretch", "name": "Немає пакування в стрейч", "fixed": 1500},
        ]
    },
    {
        "id": "candlesticks_small",
        "name": "Свічники (до 30 см)",
        "damages": [
            {"type": "dirty_wax", "name": "Брудні (віск, залишки свічок)", "min": 50, "max": 400},
            {"type": "chips_scratches", "name": "Скол або подряпини", "min": 100, "max": "full"},
            {"type": "broken", "name": "Зламані", "full": True},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "fixed": 60},
            {"type": "no_packaging", "name": "Без рідного пакування", "min": 200},
            {"type": "wet", "name": "Мокрі або вологі", "fixed": 100},
        ]
    },
    {
        "id": "candlesticks_medium",
        "name": "Свічники / канделябри (30 см - 1 м)",
        "damages": [
            {"type": "dirty_wax", "name": "Брудні (віск, залишки свічок)", "min": 100, "max": 800},
            {"type": "chips_scratches", "name": "Скол або подряпини", "min": 100, "max": "full"},
            {"type": "broken", "name": "Зламані", "full": True},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "min": 100, "max": 500},
            {"type": "no_packaging", "name": "Без рідного пакування", "min": 400, "max": 1000},
            {"type": "wet", "name": "Мокрі або вологі", "fixed": 200},
        ]
    },
    {
        "id": "candlesticks_large",
        "name": "Канделябри (1.2 - 1.8 м)",
        "damages": [
            {"type": "dirty_wax", "name": "Брудні (віск, залишки свічок)", "min": 800, "max": 1800},
            {"type": "chips_scratches", "name": "Скол або подряпини", "min": 500, "max": "full"},
            {"type": "broken", "name": "Зламані", "full": True},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "fixed": 500},
            {"type": "no_packaging", "name": "Без рідного пакування", "min": 600, "max": 1200},
            {"type": "wet", "name": "Мокрі або вологі", "fixed": 400},
        ]
    },
    {
        "id": "vases",
        "name": "Вази",
        "damages": [
            {"type": "dirty_oasis", "name": "Брудні (оазис, залишки квітів, віск)", "min": 50, "max": 2000},
            {"type": "chips_scratches", "name": "Скол або подряпини", "min": 200, "max": "full"},
            {"type": "wet_inside", "name": "З водою всередині, мокрі", "min": 50, "max": 800},
            {"type": "broken", "name": "Зламані", "full": True},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "min": 100, "max": 500},
            {"type": "no_packaging", "name": "Без рідного пакування", "min": 200, "max": 800},
        ]
    },
    {
        "id": "dishes",
        "name": "Посуд",
        "damages": [
            {"type": "dirty_oasis", "name": "Брудні (оазис, залишки квітів, їжі)", "min": 60, "max": 800},
            {"type": "chips_scratches", "name": "Скол або подряпини", "min": 200, "max": "full"},
            {"type": "wet_inside", "name": "З водою всередині, мокрі", "min": 60, "max": 200},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "fixed": 100},
            {"type": "no_packaging", "name": "Без рідного пакування", "min": 400},
        ]
    },
    {
        "id": "textile",
        "name": "Текстиль",
        "note": "Звичайне прання входить у вартість оренди",
        "damages": [
            {"type": "dirty_stains", "name": "Брудні (плями від їжі, напоїв, віск)", "min": 50, "max": 3500},
            {"type": "wet", "name": "Вологі або мокрі", "min": 300, "max": 3000},
            {"type": "burn_hole", "name": "Пропал або дірка", "full": True},
            {"type": "no_packaging", "name": "Без фірмового пакування (текстильна сумка)", "fixed": 600},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "min": 50, "max": 500},
        ]
    },
    {
        "id": "carpets",
        "name": "Килими",
        "damages": [
            {"type": "dirty", "name": "Брудні", "min": 2000, "max": 5000},
            {"type": "burn_hole", "name": "Пропал або дірка", "full": True},
            {"type": "snag_restoration", "name": "Затяжка або інше пошкодження", "min": 1000, "max": "full"},
            {"type": "wet", "name": "Вологі або мокрі", "min": 1000, "max": 2500},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "min": 200, "max": 800},
        ]
    },
    {
        "id": "tech",
        "name": "Техніка",
        "damages": [
            {"type": "dirty", "name": "Брудні", "min": 200, "max": 1200},
            {"type": "wet", "name": "Вологі або мокрі", "min": 50, "max": 400},
            {"type": "chips_scratches", "name": "Скол або подряпини", "min": 500, "max": 1200},
            {"type": "broken_misuse", "name": "Поломка або неналежне використання", "min": 1000, "max": "full"},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "min": 100, "max": 500},
        ]
    },
    {
        "id": "acrylic_cubes",
        "name": "Акрилові куби",
        "damages": [
            {"type": "dirty", "name": "Брудні", "min": 800},
            {"type": "chips_scratches", "name": "Сколи або подряпини", "fixed": 6000},
            {"type": "stickers", "name": "З залишками оракалу або інших наліпок", "min": 900},
            {"type": "paint", "name": "В фарбі", "min": 1200},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "fixed": 2000},
            {"type": "broken", "name": "Зламані", "full": True},
            {"type": "wet", "name": "Мокрі або вологі", "fixed": 200},
        ]
    },
    {
        "id": "light_decorations",
        "name": "Світлові декорації",
        "damages": [
            {"type": "dirty", "name": "Брудні", "min": 500, "max": 5000},
            {"type": "chips_scratches", "name": "Скол або подряпини", "min": 200, "max": "full"},
            {"type": "broken", "name": "Бій, зламані", "full": True},
            {"type": "wet", "name": "Вологі або мокрі", "min": 100, "max": "full"},
            {"type": "disassembled", "name": "Розібрані (гірлянди не складені)", "fixed": 250},
            {"type": "restoration_needed", "name": "Потребують реставрації", "min": 2500, "max": 15000},
            {"type": "no_packaging", "name": "Без пакування", "min": 100, "max": 1000},
        ]
    },
    {
        "id": "mirror_balls",
        "name": "Дзеркальні кулі",
        "damages": [
            {"type": "dirty", "name": "Брудні", "min": 500, "max": 1000},
            {"type": "chips_scratches", "name": "Скол, подряпини", "min": 300, "max": 3000},
            {"type": "broken", "name": "Бій", "full": True},
            {"type": "structure_damage", "name": "Порушення цілісності конструкції", "min": 1000, "max": 15000},
            {"type": "wet", "name": "Вологі або мокрі", "min": 500, "max": 3000},
            {"type": "no_packaging", "name": "Без пакування", "fixed": 2000},
        ]
    },
    {
        "id": "gypsum_figures",
        "name": "Фігури гіпс",
        "damages": [
            {"type": "broken", "name": "Бій", "full": True},
            {"type": "chips_scratches", "name": "Подряпини, скол (реставрація)", "min": 1000, "max": 2000},
            {"type": "wet", "name": "Вологі або мокрі", "min": 500, "max": 1000},
            {"type": "no_stretch", "name": "Без пакування в стрейч", "min": 100, "max": 500},
            {"type": "no_packaging", "name": "Без пакування", "percent": 30, "max_percent": 50},
        ]
    },
    {
        "id": "props",
        "name": "Реквізит",
        "damages": [
            {"type": "dirty", "name": "Брудний", "min": 100, "max": 3000},
            {"type": "wet", "name": "Вологий або мокрий", "min": 50, "max": 2000},
            {"type": "damaged_incomplete", "name": "Пошкоджений, відсутність комплектації", "min": 200, "max": 3000},
            {"type": "broken_lost", "name": "Пошкоджений (експлуатація неможлива), втрата", "full": True},
            {"type": "no_packaging", "name": "Відсутність пакування", "min": 100, "max": 500},
        ]
    },
]


def get_damage_price_range(damage_rule, product_price=None):
    """
    Calculate damage price range based on rule
    Returns tuple (min_price, max_price, description)
    """
    if damage_rule.get("full"):
        return (product_price, product_price, "Повне відшкодування")
    
    if "fixed" in damage_rule:
        return (damage_rule["fixed"], damage_rule["fixed"], f"{damage_rule['fixed']} грн")
    
    if "percent" in damage_rule:
        if product_price:
            price = int(product_price * damage_rule["percent"] / 100)
            return (price, price, f"{damage_rule['percent']}% від повного збитку")
        return (None, None, f"{damage_rule['percent']}% від повного збитку")
    
    min_price = damage_rule.get("min", 0)
    max_price = damage_rule.get("max")
    
    if max_price == "full":
        max_price = product_price
        return (min_price, max_price, f"від {min_price} грн до повного відшкодування")
    
    if max_price:
        return (min_price, max_price, f"{min_price}–{max_price} грн")
    
    return (min_price, None, f"від {min_price} грн")


def find_damage_category(product_category):
    """Find damage category by product category name"""
    category_mapping = {
        "меблі": "furniture",
        "стільці": "chairs",
        "столи": "tables",
        "пуфи": "poufs_textile_chairs",
        "вази": "vases",
        "посуд": "dishes",
        "свічники": "candlesticks_small",
        "канделябри": "candlesticks_medium",
        "текстиль": "textile",
        "килими": "carpets",
        "техніка": "tech",
        "акрил": "acrylic_cubes",
        "світло": "light_decorations",
        "дзеркал": "mirror_balls",
        "гіпс": "gypsum_figures",
        "реквізит": "props",
    }
    
    lower_category = (product_category or "").lower()
    for key, value in category_mapping.items():
        if key in lower_category:
            for cat in DAMAGE_CATEGORIES:
                if cat["id"] == value:
                    return cat
    return None
