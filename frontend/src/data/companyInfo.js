/**
 * FarforDecorOrenda Company Information
 * © FarforDecorOrenda 2025
 * Based on official documents from farforrent.com.ua
 */

export const COMPANY_INFO = {
  name: 'FarforDecorOrenda',
  legalName: 'ФОП Арсалані Олександра Ігорівна',
  taxId: '3234423422',
  address: '61082, Харківська обл., місто Харків, ПРОСПЕКТ МОСКОВСЬКИЙ, будинок 216/3А, квартира 46',
  warehouseAddress: 'Військовий провулок 1',
  email: 'rfarfordecor@gmail.com.ua',
  website: 'https://www.farforrent.com.ua',
  year: 2025,
};

export const WORKING_HOURS = {
  orderProcessing: {
    days: 'пн–пт',
    hours: '10:00–18:00',
  },
  issueReturn: {
    days: 'пн-сб',
    hours: '10:00–17:00',
  },
  afterHoursFee: 1500, // грн за вихід працівника в неробочий час
};

export const RENTAL_TERMS = {
  minOrderAmount: 2000, // мінімальна сума замовлення
  discountThreshold: 30000, // поріг для знижки 10%
  discountPercent: 10,
  urgentOrderSurcharge: 30, // % доплата за термінове замовлення (менше 24 год)
  lateReturnFee: 'добова_оренда', // автоматичне нарахування наступної доби
  minRentalPeriod: 1, // доба
  depositRule: '50% від повної вартості можливого збитку',
};

export const PAYMENT_TERMS = {
  advancePayment: 50, // % передоплата
  finalPayment: 50, // % при поверненні
  fullPrepayment: 100, // можлива 100% передоплата
  methods: ['безготівковий переказ'],
  cancellationPolicy: '2 доби до оренди — повернення авансу; менше — без повернення',
};

export const DELIVERY_TERMS = {
  selfPickup: 'Військовий провулок 1',
  novaPoshta: {
    enabled: true,
    insuranceRequired: true, // обов'язкова повна оціночна вартість
    costPaidBy: 'Орендар',
  },
  loadingResponsibility: 'Орендар або його вантажники',
};

export const DAMAGE_RULES = {
  inspectionPeriod: 14, // днів на виявлення прихованих недоліків
  photoDocumentation: true, // фотографування габаритного декору
  categories: [
    { code: 'LOST', name: 'Втрата', rule: 'повна вартість' },
    { code: 'DAMAGED', name: 'Пошкодження', rule: 'вартість ремонту або повна вартість' },
    { code: 'DIRTY', name: 'Брудний/мокрий', rule: 'згідно з прайсом збитків' },
    { code: 'PACKAGING', name: 'Втрата пакування', rule: 'нараховуються збитки' },
  ],
  penaltyCalculation: 'штрафні санкції 0.5% за кожен день прострочення',
};

export const RENTAL_PERIOD_RULES = [
  // 2 доби
  { issue: 'понеділок', return: 'четвер до 17:00', days: 2 },
  { issue: 'вівторок', return: 'п\'ятниця до 17:00', days: 2 },
  { issue: 'середа', return: 'субота до 17:00', days: 2 },
  { issue: 'п\'ятниця', return: 'понеділок до 17:00', days: 2 },
  { issue: 'субота', return: 'вівторок до 17:00', days: 2 },
  // 1 доба
  { issue: 'понеділок', return: 'середа до 17:00', days: 1 },
  { issue: 'вівторок', return: 'четвер до 17:00', days: 1 },
  { issue: 'середа', return: 'п\'ятниця до 17:00', days: 1 },
  { issue: 'четвер', return: 'субота до 17:00', days: 1 },
  { issue: 'п\'ятниця', return: 'субота до 17:00', days: 1 },
  { issue: 'субота', return: 'понеділок до 17:00', days: 1 },
];

export const RESPONSIBILITIES = {
  landlord: [
    'Підготувати замовлення вчасно і в погодженій комплектації',
    'Попередити та запропонувати альтернативу у разі відсутності позиції',
    'Передати Обладнання у технічно справному стані',
    'Ознайомити з правилами експлуатації',
  ],
  tenant: [
    'Внесення коректних дат видачі та повернення',
    'Відповідальність за стан декору під час завантаження, перевезення, використання',
    'Забезпечення вантажників',
    'Перевірка кількості і комплектації при отриманні',
    'Повернення запакованим так само, як при отриманні',
    'Своєчасна сплата орендної плати та застави',
  ],
};

export const LEGAL_LINKS = {
  terms: 'https://www.farforrent.com.ua/terms',
  privacy: 'https://www.farforrent.com.ua/privacy',
  offer: 'https://www.farforrent.com.ua/oferta',
  damageRules: 'https://www.farforrent.com.ua/opis-zbitk%D1%96v',
};

export default {
  COMPANY_INFO,
  WORKING_HOURS,
  RENTAL_TERMS,
  PAYMENT_TERMS,
  DELIVERY_TERMS,
  DAMAGE_RULES,
  RENTAL_PERIOD_RULES,
  RESPONSIBILITIES,
  LEGAL_LINKS,
};
