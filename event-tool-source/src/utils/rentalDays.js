/**
 * Логіка перерахунку діб оренди (Farfor Decor правила).
 * Клієнтська орієнтовна — менеджер фіналізує в RentalHub.
 *
 * Правила (повернення завжди до 17:00):
 *   1 доба:
 *     Пн → Ср,  Вт → Чт,  Ср → Пт,  Чт → Сб,  Пт → Сб,  Сб → Пн
 *   2 доби:
 *     Пн → Чт,  Вт → Пт,  Ср → Сб,  Пт → Пн,  Сб → Вт
 *
 * dayOfWeek: 0=Нд, 1=Пн, 2=Вт, 3=Ср, 4=Чт, 5=Пт, 6=Сб
 */

const RULES = {
  // pickup_dow → { return_dow: [billable_days, ...]}
  // ключ — день видачі, значення — мапа day_of_week_return → days_billed
  1: { 3: 1, 4: 2 },                  // Пн: Ср=1, Чт=2
  2: { 4: 1, 5: 2 },                  // Вт: Чт=1, Пт=2
  3: { 5: 1, 6: 2 },                  // Ср: Пт=1, Сб=2
  4: { 6: 1 },                        // Чт: Сб=1
  5: { 6: 1, 1: 2 },                  // Пт: Сб=1, Пн=2
  6: { 1: 1, 2: 2 },                  // Сб: Пн=1, Вт=2
};

const DOW_NAMES_UK = ['неділя', 'понеділок', 'вівторок', 'середа', 'четвер', 'пʼятниця', 'субота'];

/**
 * Розрахунок діб оренди за правилами Farfor Decor.
 * @param {Date|string} pickupDate
 * @param {Date|string} returnDate
 * @returns {{ days: number, isStandard: boolean, hint: string }}
 *   days — кількість оплачуваних діб
 *   isStandard — чи відповідає таблиці (true) чи fallback по календарних днях (false)
 *   hint — повідомлення для UI
 */
export function calculateRentalDays(pickupDate, returnDate) {
  if (!pickupDate || !returnDate) {
    return { days: 0, isStandard: false, hint: 'Вкажіть дати видачі та повернення' };
  }

  const pickup = new Date(pickupDate);
  const ret = new Date(returnDate);
  if (isNaN(pickup) || isNaN(ret)) {
    return { days: 0, isStandard: false, hint: 'Некоректні дати' };
  }

  // Нормалізуємо до півночі
  pickup.setHours(0, 0, 0, 0);
  ret.setHours(0, 0, 0, 0);

  if (ret < pickup) {
    return { days: 0, isStandard: false, hint: 'Дата повернення раніша за видачу' };
  }

  const pickupDow = pickup.getDay();
  const returnDow = ret.getDay();
  const calendarDays = Math.round((ret - pickup) / (1000 * 60 * 60 * 24));

  // Стандартний тариф з таблиці — для робочих днів видачі (Пн-Сб) і коли різниця ≤ 7 днів
  const rule = RULES[pickupDow];
  if (rule && calendarDays <= 6 && rule[returnDow] !== undefined) {
    const days = rule[returnDow];
    return {
      days,
      isStandard: true,
      hint: `${DOW_NAMES_UK[pickupDow]} → ${DOW_NAMES_UK[returnDow]} = ${days} ${days === 1 ? 'доба' : 'доби'} (повернення до 17:00)`,
    };
  }

  // Fallback: якщо нестандартна комбінація — рахуємо як calendar days, але мінімум 1
  const days = Math.max(1, calendarDays);
  return {
    days,
    isStandard: false,
    hint: `Орієнтовно ${days} ${days === 1 ? 'доба' : days < 5 ? 'доби' : 'діб'}. Менеджер уточнить фінальний тариф.`,
  };
}

/**
 * Час видачі — слоти.
 */
export const PICKUP_TIME_SLOTS = [
  { value: '09:00-10:00', label: '09:00–10:00' },
  { value: '10:00-11:00', label: '10:00–11:00' },
  { value: '11:00-12:00', label: '11:00–12:00' },
  { value: '11:30-12:00', label: '11:30–12:00' },
  { value: '12:00-13:00', label: '12:00–13:00' },
  { value: '13:00-14:00', label: '13:00–14:00' },
  { value: '14:00-15:00', label: '14:00–15:00' },
  { value: '15:00-16:00', label: '15:00–16:00' },
  { value: '16:00-17:00', label: '16:00–17:00' },
];

/**
 * Час повернення — фіксовано до 17:00 (правило компанії).
 */
export const RETURN_TIME = '17:00';
