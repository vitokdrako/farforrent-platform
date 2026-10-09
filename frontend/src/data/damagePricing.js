/**
 * Damage Pricing Rules - Тарифи на відшкодування пошкоджень
 * © FarforDecorOrenda 2025
 * Source: https://www.farforrent.com.ua/opis-zbitkiv
 */

export const DAMAGE_CATEGORIES = [
  {
    id: 'furniture',
    name: 'Меблі',
    nameUk: 'Меблі',
    damages: [
      { type: 'dirty_upholstery', name: 'Брудна оббивка / сидіння / каркас', price: { min: 1000 } },
      { type: 'chips_scratches', name: 'Скол, подряпини, тріщини, втрата деталей', price: { min: 800, max: 'full' } },
      { type: 'burn_hole', name: 'Пропал або дірка', price: { min: 5000 } },
      { type: 'dirty_legs', name: 'Ніжки брудні в землі/глині/піску', price: { min: 800 } },
      { type: 'liquid_spill', name: 'Залито рідиною (вода, вино, сік та інше)', price: { min: 1000, max: 2500 } },
      { type: 'wet', name: 'Мокрі або вологі (вода)', price: { min: 1000, max: 2000 } },
      { type: 'no_cover', name: 'Немає фірмового чохла', price: { fixed: 1400 } },
      { type: 'no_stretch', name: 'Немає пакування в стрейч', price: { min: 500, max: 1000 } },
    ]
  },
  {
    id: 'tables',
    name: 'Столики',
    nameUk: 'Столики',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 500 } },
      { type: 'chips_scratches', name: 'Сколи або подряпини', price: { min: 1600, max: 3000 } },
      { type: 'damaged_top', name: 'Відсутня або пошкоджена столешня', price: { min: 1500 } },
      { type: 'no_stretch', name: 'Без стрейчування', price: { percent: 30 } },
      { type: 'no_packaging', name: 'Без власного пакування (фірмові чохли, «рідні коробки»)', price: { percent: 50 } },
    ]
  },
  {
    id: 'poufs_textile_chairs',
    name: 'Пуфи та стільці з текстилем (шкірою)',
    nameUk: 'Пуфи та стільці з текстилем',
    damages: [
      { type: 'dirty_upholstery', name: 'Брудна оббивка або сидіння', price: { min: 1200, max: 2000 } },
      { type: 'damaged_frame', name: 'Пошкоджений каркас', price: { min: 700 } },
      { type: 'dirty_legs', name: 'Ніжки брудні в землі/глині/піску', price: { min: 800 } },
      { type: 'burn_hole', name: 'Пропал або дірка', price: { full: true } },
      { type: 'liquid_spill', name: 'Залито рідиною (вода, вино, сік та інше)', price: { min: 1200, max: 2000 } },
      { type: 'wet', name: 'Мокрі або вологі (вода)', price: { min: 1000, max: 2000 } },
      { type: 'no_cover', name: 'Немає фірмового чохла або рідної коробки', price: { fixed: 3000 } },
      { type: 'no_stretch', name: 'Немає пакування в стрейч', price: { fixed: 1500 } },
    ]
  },
  {
    id: 'chairs',
    name: 'Стільці',
    nameUk: 'Стільці',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 700 } },
      { type: 'chips_scratches', name: 'Сколи або подряпини', price: { fixed: 1500 } },
      { type: 'no_stretch', name: 'Без стрейчування', price: { fixed: 1000 } },
      { type: 'wet', name: 'Мокрі або вологі', price: { fixed: 1000 } },
      { type: 'broken', name: 'Зламані, пошкодження які унеможливлюють використання', price: { full: true } },
    ]
  },
  {
    id: 'pedestals',
    name: 'Тумби / постаменти',
    nameUk: 'Тумби / постаменти',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 800 } },
      { type: 'chips_scratches', name: 'Скол, подряпини, тріщини, втрата деталей', price: { min: 500, max: 'full' } },
      { type: 'stickers', name: 'З залишками оракалу або інших наліпок', price: { min: 500 } },
      { type: 'paint', name: 'В фарбі', price: { min: 800 } },
      { type: 'no_packaging', name: 'Без власного пакування (деревʼяний бокс, чохол)', price: { fixed: 2800 } },
      { type: 'no_stretch', name: 'Без пакування в стрейч і захисних елементів', price: { min: 500, max: 1000 } },
      { type: 'broken', name: 'Пошкодження, що унеможливлюють використання', price: { full: true } },
      { type: 'wet', name: 'Мокрі або вологі', price: { min: 200 } },
    ]
  },
  {
    id: 'candlesticks_small',
    name: 'Свічники (h: до 30 см)',
    nameUk: 'Свічники (до 30 см)',
    damages: [
      { type: 'dirty_wax', name: 'Брудні (віск, залишки свічок, сліди горіння)', price: { min: 50, max: 400 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 100, max: 'full' } },
      { type: 'broken', name: 'Зламані, пошкодження які унеможливлюють використання', price: { full: true } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { fixed: 60 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { min: 200 } },
      { type: 'wet', name: 'Мокрі або вологі', price: { fixed: 100 } },
    ]
  },
  {
    id: 'candlesticks_medium',
    name: 'Свічники / канделябри (h: 30 см – 1 м)',
    nameUk: 'Свічники / канделябри (30 см - 1 м)',
    damages: [
      { type: 'dirty_wax', name: 'Брудні (віск, залишки свічок, сліди горіння)', price: { min: 100, max: 800 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 100, max: 'full' } },
      { type: 'broken', name: 'Зламані, пошкодження які унеможливлюють використання', price: { full: true } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 100, max: 500 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { min: 400, max: 1000 } },
      { type: 'wet', name: 'Мокрі або вологі', price: { fixed: 200 } },
    ]
  },
  {
    id: 'candlesticks_large',
    name: 'Канделябри (h: 1,2 м – 1,8 м)',
    nameUk: 'Канделябри (1.2 - 1.8 м)',
    damages: [
      { type: 'dirty_wax', name: 'Брудні (віск, залишки свічок, сліди горіння)', price: { min: 800, max: 1800 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 500, max: 'full' } },
      { type: 'broken', name: 'Зламані, пошкодження які унеможливлюють використання', price: { full: true } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { fixed: 500 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { min: 600, max: 1200 } },
      { type: 'wet', name: 'Мокрі або вологі', price: { fixed: 400 } },
    ]
  },
  {
    id: 'candlesticks_glass',
    name: 'Канделябри скляні (тільки LED свічки)',
    nameUk: 'Канделябри скляні',
    damages: [
      { type: 'dirty_fire', name: 'Брудні (сліди живого вогню, віск тощо)', price: { min: 6000 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 300, max: 'full' } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { percent: 30 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { percent: 50 } },
      { type: 'wet', name: 'Мокрі або вологі', price: { fixed: 400 } },
    ]
  },
  {
    id: 'brass_copper',
    name: 'Латунь та мідь',
    nameUk: 'Латунь та мідь',
    damages: [
      { type: 'dirty_wax', name: 'Брудні (віск, залишки свічок, сліди горіння)', price: { min: 50, max: 800 } },
      { type: 'chip', name: 'Скол', price: { full: true } },
      { type: 'scratches', name: 'Подряпини', price: { full: true } },
      { type: 'broken', name: 'Зламані, пошкодження які унеможливлюють використання', price: { full: true } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 50, max: 500 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { percent: 50 } },
      { type: 'wet', name: 'Мокрі або вологі', price: { min: 50 } },
      { type: 'oxidation', name: 'Окислення від використання хімічних засобів', price: { full: true } },
      { type: 'coating_damage', name: 'Пошкоджене покриття', price: { full: true } },
    ]
  },
  {
    id: 'lanterns_florariums',
    name: 'Ліхтарі / флораріуми',
    nameUk: 'Ліхтарі / флораріуми',
    damages: [
      { type: 'dirty_oasis', name: 'Брудні (оазис, залишки квітів, їжі, фарба, віск, флор. матеріали)', price: { min: 100, max: 2000 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 300, max: 'full' } },
      { type: 'wet_inside', name: 'З водою всередині, мокрі, не натерті', price: { min: 400, max: 2000 } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 100, max: 500 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { percent: 50 } },
    ]
  },
  {
    id: 'crystal',
    name: 'Кришталь',
    nameUk: 'Кришталь',
    damages: [
      { type: 'dirty', name: 'Брудний', price: { min: 100, max: 500 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 200, max: 'full' } },
      { type: 'wet_inside', name: 'З водою всередині, мокрі, не натерті', price: { min: 50, max: 200 } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { percent: 30 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { percent: 50 } },
    ]
  },
  {
    id: 'composition_stands',
    name: 'Підставки під композиції',
    nameUk: 'Підставки під композиції',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 200, max: 1000 } },
      { type: 'chips_scratches', name: 'Сколи або подряпини', price: { min: 700, max: 'full' } },
      { type: 'missing_part', name: 'Відсутній або пошкоджений зйомний фрагмент', price: { min: 1000, max: 'full' } },
      { type: 'no_stretch', name: 'Без стрейчування', price: { min: 100, max: 500 } },
      { type: 'no_packaging', name: 'Без власного пакування', price: { percent: 50 } },
    ]
  },
  {
    id: 'vases',
    name: 'Вази',
    nameUk: 'Вази',
    damages: [
      { type: 'dirty_oasis', name: 'Брудні (оазис, залишки квітів, їжі, фарба, віск, наліпки)', price: { min: 50, max: 2000 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 200, max: 'full' } },
      { type: 'wet_inside', name: 'З водою всередині, мокрі, не натерті', price: { min: 50, max: 800 } },
      { type: 'broken', name: 'Зламані, пошкодження які унеможливлюють використання', price: { full: true } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 100, max: 500 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { min: 200, max: 800 } },
    ]
  },
  {
    id: 'dishes',
    name: 'Посуд',
    nameUk: 'Посуд',
    damages: [
      { type: 'dirty_oasis', name: 'Брудні (оазис, залишки квітів, їжі, фарба, віск)', price: { min: 60, max: 800 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 200, max: 'full' } },
      { type: 'wet_inside', name: 'З водою всередині, мокрі, не натерті', price: { min: 60, max: 200 } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { fixed: 100 } },
      { type: 'no_packaging', name: 'Без рідного пакування', price: { min: 400 } },
    ]
  },
  {
    id: 'hanging_objects',
    name: 'Підвісні обʼєкти',
    nameUk: 'Підвісні об\'єкти',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 500, max: 1000 } },
      { type: 'chips_scratches', name: 'Скол, порушення цілісності, подряпини', price: { min: 300, max: 'full' } },
      { type: 'wet_inside', name: 'З водою всередині, мокрі, не натерті', price: { min: 100, max: 800 } },
      { type: 'no_packaging', name: 'Без пакування в стрейч і картону/текстильного покриття', price: { min: 500, max: 1000 } },
      { type: 'no_original_packaging', name: 'Без рідного пакування', price: { percent: 50 } },
    ]
  },
  {
    id: 'acrylic_cubes',
    name: 'Акрилові куби',
    nameUk: 'Акрилові куби',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 800 } },
      { type: 'chips_scratches', name: 'Сколи або подряпини', price: { fixed: 6000 } },
      { type: 'stickers', name: 'З залишками оракалу або інших наліпок', price: { min: 900 } },
      { type: 'paint', name: 'В фарбі', price: { min: 1200 } },
      { type: 'no_stretch', name: 'Без пакування в стрейч і захисні елементи', price: { fixed: 2000 } },
      { type: 'broken', name: 'Зламані', price: { full: true } },
      { type: 'wet', name: 'Мокрі або вологі', price: { fixed: 200 } },
    ]
  },
  {
    id: 'mirror_balls',
    name: 'Дзеркальні кулі',
    nameUk: 'Дзеркальні кулі',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 500, max: 1000 } },
      { type: 'chips_scratches', name: 'Скол, подряпини або втрата деталей', price: { min: 300, max: 3000 } },
      { type: 'broken', name: 'Бій, пошкодження які унеможливлюють використання', price: { full: true } },
      { type: 'structure_damage', name: 'Порушення цілісності конструкції', price: { min: 1000, max: 15000 } },
      { type: 'wet', name: 'Вологі або мокрі', price: { min: 500, max: 3000 } },
      { type: 'no_packaging', name: 'Без пакування (чохол, бокс, фірмова коробка)', price: { fixed: 2000 } },
    ]
  },
  {
    id: 'light_decorations',
    name: 'Світлові декорації',
    nameUk: 'Світлові декорації',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 500, max: 5000 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 200, max: 'full' } },
      { type: 'broken', name: 'Бій, зламані, пошкодження які унеможливлюють використання', price: { full: true } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 100, max: 'full' } },
      { type: 'disassembled', name: 'Розібрані (гірлянди не складені)', price: { fixed: 250 } },
      { type: 'restoration_needed', name: 'Пошкодження які потребують подальшого реставрування', price: { min: 2500, max: 15000 } },
      { type: 'no_packaging', name: 'Без пакування (чохол, бокс, фірмова коробка)', price: { min: 100, max: 1000 } },
    ]
  },
  {
    id: 'gypsum_figures',
    name: 'Фігури гіпс (бюст, голови)',
    nameUk: 'Фігури гіпс',
    damages: [
      { type: 'broken', name: 'Бій', price: { full: true } },
      { type: 'chips_scratches', name: 'Подряпини, скол (реставрація)', price: { min: 1000, max: 2000 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 500, max: 1000 } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 100, max: 500 } },
      { type: 'no_packaging', name: 'Без пакування (чохол, бокс, фірмова коробка)', price: { percent: 30, maxPercent: 50 } },
    ]
  },
  {
    id: 'textile',
    name: 'Текстиль',
    nameUk: 'Текстиль',
    note: 'Звичайне прання входить у вартість оренди',
    damages: [
      { type: 'dirty_stains', name: 'Брудні (плями від їжі, напоїв, віск)', price: { min: 50, max: 3500 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 300, max: 3000 } },
      { type: 'burn_hole', name: 'Пропал або дірка', price: { full: true } },
      { type: 'no_packaging', name: 'Без фірмового пакування (текстильна сумка)', price: { fixed: 600 } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 50, max: 500 } },
    ]
  },
  {
    id: 'carpets',
    name: 'Килими',
    nameUk: 'Килими',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 2000, max: 5000 } },
      { type: 'burn_hole', name: 'Пропал або дірка', price: { full: true } },
      { type: 'snag_restoration', name: 'Затяжка або інше пошкодження, яке потребує реставрації', price: { min: 1000, max: 'full' } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 1000, max: 2500 } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 200, max: 800 } },
    ]
  },
  {
    id: 'tech',
    name: 'Техніка',
    nameUk: 'Техніка',
    damages: [
      { type: 'dirty', name: 'Брудні (земля, глина, фарба, флористичний матеріал)', price: { min: 200, max: 1200 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 50, max: 400 } },
      { type: 'chips_scratches', name: 'Скол або подряпини', price: { min: 500, max: 1200 } },
      { type: 'broken_misuse', name: 'Поломка або неналежне використання', price: { min: 1000, max: 'full' } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 100, max: 500 } },
    ]
  },
  {
    id: 'ethnic',
    name: 'Етно',
    nameUk: 'Етно',
    damages: [
      { type: 'dirty', name: 'Брудний реквізит', price: { min: 100, max: 2000 } },
      { type: 'wet', name: 'Вологий або мокрий (вода)', price: { min: 100, max: 2000 } },
      { type: 'chips_scratches', name: 'Скол, подряпина або інший вид пошкодження', price: { min: 200, max: 'full' } },
      { type: 'no_packaging', name: 'Відсутність пакування як при видачі', price: { min: 100, max: 500 } },
    ]
  },
  {
    id: 'table_numbers',
    name: 'Нумерація столів (рамки, тримачі карток)',
    nameUk: 'Нумерація столів',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 100, max: 500 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 50, max: 300 } },
      { type: 'broken', name: 'Пошкоджені', price: { full: true } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 50 } },
      { type: 'no_packaging', name: 'Без рідного пакування (конверт, коробка)', price: { fixed: 200 } },
    ]
  },
  {
    id: 'decorative_flowers',
    name: 'Декоративна квітка',
    nameUk: 'Декоративна квітка',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 50, max: 1000 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { fixed: 50 } },
      { type: 'damaged_restoration', name: 'Пошкоджені (можлива реставрація)', price: { min: 100, max: 1000 } },
      { type: 'no_packaging', name: 'Відсутність пакування (чохол або пластиковий бокс)', price: { min: 600 } },
    ]
  },
  {
    id: 'mirrors_frames',
    name: 'Дзеркала / рамки',
    nameUk: 'Дзеркала / рамки',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 400, max: 2000 } },
      { type: 'stickers', name: 'З залишками оракалу або інших наліпок', price: { min: 400, max: 2000 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 200, max: 800 } },
      { type: 'damaged_missing', name: 'Пошкоджені, втрата деталей та елементів', price: { min: 1000, max: 'full' } },
      { type: 'no_packaging', name: 'Без пакування (гофро картон та стрейч-плівка)', price: { min: 500, max: 1000 } },
    ]
  },
  {
    id: 'boxes',
    name: 'Скриньки',
    nameUk: 'Скриньки',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 100, max: 600 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 100, max: 'full' } },
      { type: 'damaged_incomplete', name: 'Пошкоджені (можлива реставрація), відсутність комплектації', price: { min: 300, max: 'full' } },
      { type: 'broken_lost', name: 'Пошкоджені (експлуатація неможлива), втрата', price: { full: true } },
      { type: 'no_stretch', name: 'Без пакування в стрейч', price: { min: 50 } },
      { type: 'no_packaging', name: 'Без рідного пакування (конверт, коробка)', price: { min: 300 } },
    ]
  },
  {
    id: 'games',
    name: 'Ігри',
    nameUk: 'Ігри',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 100, max: 'full' } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 100, max: 'full' } },
      { type: 'damaged_incomplete', name: 'Пошкоджені (можлива реставрація), відсутність комплектації', price: { min: 500, max: 'full' } },
      { type: 'broken_lost', name: 'Пошкоджені (експлуатація неможлива), втрата', price: { full: true } },
      { type: 'no_packaging', name: 'Відсутність пакування як при видачі', price: { min: 100, max: 500 } },
    ]
  },
  {
    id: 'cages',
    name: 'Клітки',
    nameUk: 'Клітки',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 100, max: 1500 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 100, max: 500 } },
      { type: 'damaged_incomplete', name: 'Пошкоджені (можлива реставрація), відсутність комплектації', price: { min: 800, max: 'full' } },
      { type: 'broken_lost', name: 'Пошкоджені (експлуатація неможлива), втрата', price: { full: true } },
      { type: 'no_packaging', name: 'Відсутність пакування як при видачі', price: { min: 100, max: 500 } },
    ]
  },
  {
    id: 'constructions',
    name: 'Конструктиви',
    nameUk: 'Конструктиви',
    damages: [
      { type: 'dirty', name: 'Брудні', price: { min: 300, max: 4000 } },
      { type: 'wet', name: 'Вологі або мокрі (вода)', price: { min: 200, max: 'full' } },
      { type: 'damaged_incomplete', name: 'Пошкоджені (можлива реставрація), відсутність комплектації', price: { min: 1500, max: 'full' } },
      { type: 'broken_lost', name: 'Пошкоджені (експлуатація неможлива), втрата', price: { full: true } },
      { type: 'no_packaging', name: 'Відсутність пакування як при видачі', price: { min: 100, max: 500 } },
    ]
  },
  {
    id: 'props',
    name: 'Реквізит',
    nameUk: 'Реквізит',
    damages: [
      { type: 'dirty', name: 'Брудний', price: { min: 100, max: 3000 } },
      { type: 'wet', name: 'Вологий або мокрий (вода)', price: { min: 50, max: 2000 } },
      { type: 'damaged_incomplete', name: 'Пошкоджений (можлива реставрація), відсутність комплектації', price: { min: 200, max: 3000 } },
      { type: 'broken_lost', name: 'Пошкоджений (експлуатація неможлива), втрата', price: { full: true } },
      { type: 'no_packaging', name: 'Відсутність пакування як при видачі', price: { min: 100, max: 500 } },
    ]
  },
  {
    id: 'new_year',
    name: 'Новий рік',
    nameUk: 'Новий рік',
    damages: [
      { type: 'dirty', name: 'Брудний', price: { min: 100, max: 5000 } },
      { type: 'wet', name: 'Вологий або мокрий (вода)', price: { min: 50, max: 4000 } },
      { type: 'damaged_incomplete', name: 'Пошкоджений (можлива реставрація), відсутність комплектації', price: { min: 200, max: 'full' } },
      { type: 'broken_lost', name: 'Пошкоджені (експлуатація неможлива), втрата', price: { full: true } },
      { type: 'no_packaging', name: 'Відсутність пакування як при видачі', price: { min: 100, max: 500 } },
    ]
  },
  {
    id: 'black_box',
    name: 'Розкладний чорний бокс',
    nameUk: 'Розкладний чорний бокс',
    damages: [
      { type: 'dirty', name: 'Брудний', price: { min: 100, max: 400 } },
      { type: 'wet', name: 'Мокрий', price: { min: 50, max: 200 } },
      { type: 'lost_damaged', name: 'Втрата або пошкодження', price: { fixed: 900 } },
    ]
  },
];

// Helper function to format price
export function formatDamagePrice(price, productPrice = null) {
  if (price.full) return 'Повне відшкодування';
  if (price.fixed) return `${price.fixed} грн`;
  if (price.percent) {
    const percentText = `${price.percent}% від повного збитку`;
    if (productPrice) return `${Math.round(productPrice * price.percent / 100)} грн (${percentText})`;
    return percentText;
  }
  if (price.min && price.max === 'full') return `від ${price.min} грн до повного відшкодування`;
  if (price.min && price.max) return `${price.min}–${price.max} грн`;
  if (price.min) return `від ${price.min} грн`;
  return 'Уточнюється';
}

// Find category by product type/category
export function findDamageCategoryByProductType(productCategory) {
  const categoryMapping = {
    'меблі': 'furniture',
    'стільці': 'chairs',
    'столи': 'tables',
    'пуфи': 'poufs_textile_chairs',
    'вази': 'vases',
    'посуд': 'dishes',
    'свічники': 'candlesticks_small',
    'канделябри': 'candlesticks_medium',
    'текстиль': 'textile',
    'килими': 'carpets',
    // Add more mappings as needed
  };
  
  const lowerCategory = (productCategory || '').toLowerCase();
  for (const [key, value] of Object.entries(categoryMapping)) {
    if (lowerCategory.includes(key)) {
      return DAMAGE_CATEGORIES.find(c => c.id === value);
    }
  }
  return null;
}

export default DAMAGE_CATEGORIES;
