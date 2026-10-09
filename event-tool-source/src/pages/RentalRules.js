/**
 * RentalRules — статична сторінка з правилами оренди.
 * Доступна за маршрутом /rules.
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';

const Section = ({ title, children }) => (
  <div style={{marginBottom: '28px'}}>
    <h3 style={{
      fontSize: '15px', fontWeight: '700', color: '#0a3d2e',
      textTransform: 'uppercase', letterSpacing: '1px',
      marginBottom: '10px', paddingBottom: '8px',
      borderBottom: '1px solid #e2e8f0',
    }}>
      {title}
    </h3>
    <div style={{fontSize: '14px', color: '#334155', lineHeight: '1.6'}}>
      {children}
    </div>
  </div>
);

const RentalRules = () => {
  const navigate = useNavigate();

  return (
    <div style={{minHeight: '100vh', background: '#fff'}}>
      {/* Header */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 10,
        padding: '14px 16px', background: '#fff',
        borderBottom: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: '12px',
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{background: 'transparent', border: 'none', fontSize: '22px', cursor: 'pointer', color: '#0f172a', padding: 0}}
          aria-label="Назад"
        >‹</button>
        <h1 style={{fontSize: '17px', fontWeight: '700', color: '#0f172a', margin: 0}}>
          Правила оренди
        </h1>
      </header>

      <div style={{maxWidth: '720px', margin: '0 auto', padding: '20px 16px 80px'}}>
        <Section title="Бронювання">
          Замовлення необхідно оформити <strong>щонайменше за 3 дні</strong> до дати івенту.
          Після підтвердження менеджером бронювання вважається активним.
        </Section>

        <Section title="Оплата та завдаток">
          <ul style={{paddingLeft: '18px', margin: 0}}>
            <li><strong>Завдаток 50%</strong> — підтверджує бронювання.</li>
            <li>Решта суми сплачується в день видачі.</li>
            <li>Окремо вноситься <strong>застава</strong> (відшкодування за пошкодження) — повертається у повному обсязі після повернення товарів у належному стані.</li>
          </ul>
        </Section>

        <Section title="Видача та повернення">
          Видача та повернення відбуваються за адресою складу або з доставкою (за окрему плату).
          Терміни вказуються при оформленні замовлення. Запізнення з поверненням понад 2 години — додатковий день оренди.
        </Section>

        <Section title="Збереження та пошкодження">
          Орендар несе повну фінансову відповідальність за збереження товарів від моменту видачі до повернення.
          У разі пошкодження або втрати — компенсація з застави або окремою оплатою.
        </Section>

        <Section title="Скасування">
          <ul style={{paddingLeft: '18px', margin: 0}}>
            <li>За <strong>7+ днів</strong> до події — повернення 100% завдатку.</li>
            <li>За <strong>3–6 днів</strong> — повернення 50%.</li>
            <li>Менше 3 днів — завдаток не повертається.</li>
          </ul>
        </Section>

        <Section title="Контакти">
          Питання щодо оренди: <strong>+38 (067) 123-45-67</strong><br />
          Email: <strong>info@farforrent.com.ua</strong>
        </Section>
      </div>
    </div>
  );
};

export default RentalRules;
