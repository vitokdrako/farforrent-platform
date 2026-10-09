/* eslint-disable */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useToast } from '../hooks/use-toast';
import axios from 'axios';

const TasksClean = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [filterPeriod, setFilterPeriod] = useState('Сьогодні');
  const [filterAssignee, setFilterAssignee] = useState('Всі');
  const [filterPriority, setFilterPriority] = useState('Всі');
  const [filterStatus, setFilterStatus] = useState('Всі');
  const [filterRelated, setFilterRelated] = useState('Всі');
  const [filterSearch, setFilterSearch] = useState('');
  
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${BACKEND_URL}/api/tasks`);
      setTasks(response.data);
    } catch (error) {
      console.error('Error loading tasks:', error);
      toast({
        title: '❌ Помилка',
        description: 'Не вдалося завантажити завдання',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const getPriorityBadge = (priority) => {
    const map = {
      low: ['bg-slate-100', 'text-slate-700', 'low'],
      medium: ['bg-sky-100', 'text-sky-800', 'medium'],
      high: ['bg-amber-100', 'text-amber-800', 'high'],
      urgent: ['bg-rose-100', 'text-rose-800', 'urgent']
    };
    return map[priority] || ['bg-slate-100', 'text-slate-700', priority];
  };

  // Group tasks by status
  const backlogTasks = tasks.filter(t => t.status === 'backlog' || t.status === 'pending');
  const todayTasks = tasks.filter(t => t.status === 'today' || t.status === 'in_progress');
  const inProgressTasks = tasks.filter(t => t.status === 'in_progress');
  const blockedTasks = tasks.filter(t => t.status === 'blocked');

  // Calculate KPIs
  const todayCount = todayTasks.length;
  const inProgressCount = inProgressTasks.length;
  const blockedCount = blockedTasks.length;
  const completedCount = tasks.filter(t => t.status === 'completed').length;

  return (
    <div className="min-h-screen bg-white text-corp-text-dark">
      {/* Topbar */}
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur supports-[backdrop-filter]:bg-white/70">
        <div className="mx-auto max-w-7xl px-6 py-3 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-full border border-slate-300 grid place-content-center font-semibold text-sm">
              FD
            </div>
            <span className="text-lg font-semibold tracking-tight">Панель завдань</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button className="h-9 rounded-xl border border-slate-200 px-3 text-sm hover:shadow">
              Експорт
            </button>
            <button className="h-9 rounded-xl bg-teal-600 px-3 text-sm text-white hover:bg-teal-700">
              Нове завдання
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-6 grid gap-6">
        {/* Filters */}
        <section className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <label className="flex flex-col gap-1 text-sm text-corp-text-main">
            <span className="font-medium">Період</span>
            <select 
              className="corp-input"
              value={filterPeriod}
              onChange={(e) => setFilterPeriod(e.target.value)}
            >
              <option>Сьогодні</option>
              <option>Тиждень</option>
              <option>Місяць</option>
              <option>Діапазон…</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm text-corp-text-main">
            <span className="font-medium">Виконавець</span>
            <select 
              className="corp-input"
              value={filterAssignee}
              onChange={(e) => setFilterAssignee(e.target.value)}
            >
              <option>Всі</option>
              <option>Вікторія</option>
              <option>Богдан</option>
              <option>Склад</option>
              <option>DevOps</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm text-corp-text-main">
            <span className="font-medium">Пріоритет</span>
            <select 
              className="corp-input"
              value={filterPriority}
              onChange={(e) => setFilterPriority(e.target.value)}
            >
              <option>Всі</option>
              <option>low</option>
              <option>medium</option>
              <option>high</option>
              <option>urgent</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm text-corp-text-main">
            <span className="font-medium">Статус</span>
            <select 
              className="corp-input"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option>Всі</option>
              <option>backlog</option>
              <option>today</option>
              <option>in_progress</option>
              <option>blocked</option>
              <option>done</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm text-corp-text-main">
            <span className="font-medium">Пов'язано з</span>
            <select 
              className="corp-input"
              value={filterRelated}
              onChange={(e) => setFilterRelated(e.target.value)}
            >
              <option>Всі</option>
              <option>orders</option>
              <option>issue</option>
              <option>return</option>
              <option>finance</option>
              <option>damage</option>
              <option>catalog</option>
              <option>infra</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm text-corp-text-main">
            <span className="font-medium">Пошук</span>
            <input 
              className="corp-input" 
              placeholder="Текст / № замовлення / тег"
              value={filterSearch}
              onChange={(e) => setFilterSearch(e.target.value)}
            />
          </label>
        </section>

        {/* KPIs */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-2xl border border-slate-200 p-4 shadow-sm">
            <div className="text-sm text-corp-text-main">Завдань на сьогодні</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
              {todayCount}
            </div>
            <div className="mt-1 text-xs text-corp-text-muted">2 високий / 1 терміновий</div>
          </div>

          <div className="rounded-2xl border border-slate-200 p-4 shadow-sm bg-slate-50 text-slate-700">
            <div className="text-sm text-corp-text-main">В роботі</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
              {inProgressCount}
            </div>
            <div className="mt-1 text-xs text-corp-text-muted">пакування, фото, інвойс</div>
          </div>

          <div className="rounded-2xl border border-slate-200 p-4 shadow-sm bg-amber-50 text-amber-700">
            <div className="text-sm text-corp-text-main">Заблоковано</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
              {blockedCount}
            </div>
            <div className="mt-1 text-xs text-corp-text-muted">oc-db-ping</div>
          </div>

          <div className="rounded-2xl border border-slate-200 p-4 shadow-sm bg-emerald-50 text-emerald-700">
            <div className="text-sm text-corp-text-main">Виконано (період)</div>
            <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
              {completedCount}
            </div>
            <div className="mt-1 text-xs text-corp-text-muted">за тиждень</div>
          </div>
        </section>

        {/* Kanban Columns */}
        <main className="grid grid-cols-1 xl:grid-cols-4 gap-6">
          {/* Column 1: Backlog */}
          <section className="rounded-2xl border border-slate-200 p-4 shadow-sm ring-2 ring-slate-100">
            <header className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-semibold leading-none">Беклог</h3>
              <button className="h-8 rounded-xl border border-slate-200 px-3 text-sm hover:shadow">
                Фільтр
              </button>
            </header>
            <div className="grid gap-3">
              {loading ? (
                <div className="text-center py-8 text-corp-text-muted">Завантаження...</div>
              ) : backlogTasks.length === 0 ? (
                <div className="text-center py-8 text-corp-text-muted">Немає завдань</div>
              ) : (
                backlogTasks.slice(0, 5).map(t => <TaskCard key={t.id} task={t} getPriorityBadge={getPriorityBadge} />)
              )}
            </div>
          </section>

          {/* Column 2: Today */}
          <section className="rounded-2xl border border-slate-200 p-4 shadow-sm ring-2 ring-emerald-100">
            <header className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-semibold leading-none">Сьогодні</h3>
              <button className="h-8 rounded-xl border border-slate-200 px-3 text-sm hover:shadow">
                Фільтр
              </button>
            </header>
            <div className="grid gap-3">
              {loading ? (
                <div className="text-center py-8 text-corp-text-muted">Завантаження...</div>
              ) : todayTasks.length === 0 ? (
                <div className="text-center py-8 text-corp-text-muted">Немає завдань</div>
              ) : (
                todayTasks.slice(0, 5).map(t => <TaskCard key={t.id} task={t} getPriorityBadge={getPriorityBadge} />)
              )}
            </div>
          </section>

          {/* Column 3: In Progress */}
          <section className="rounded-2xl border border-slate-200 p-4 shadow-sm ring-2 ring-slate-100">
            <header className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-semibold leading-none">В роботі</h3>
              <button className="h-8 rounded-xl border border-slate-200 px-3 text-sm hover:shadow">
                Фільтр
              </button>
            </header>
            <div className="grid gap-3">
              {loading ? (
                <div className="text-center py-8 text-corp-text-muted">Завантаження...</div>
              ) : inProgressTasks.length === 0 ? (
                <div className="text-center py-8 text-corp-text-muted">Немає завдань</div>
              ) : (
                inProgressTasks.slice(0, 5).map(t => <TaskCard key={t.id} task={t} getPriorityBadge={getPriorityBadge} />)
              )}
            </div>
          </section>

          {/* Column 4: Blocked */}
          <section className="rounded-2xl border border-slate-200 p-4 shadow-sm ring-2 ring-amber-100">
            <header className="mb-3 flex items-center justify-between">
              <h3 className="text-base font-semibold leading-none">Заблоковано</h3>
              <button className="h-8 rounded-xl border border-slate-200 px-3 text-sm hover:shadow">
                Фільтр
              </button>
            </header>
            <div className="grid gap-3">
              {loading ? (
                <div className="text-center py-8 text-corp-text-muted">Завантаження...</div>
              ) : blockedTasks.length === 0 ? (
                <div className="text-center py-8 text-corp-text-muted">Немає завдань</div>
              ) : (
                blockedTasks.slice(0, 5).map(t => <TaskCard key={t.id} task={t} getPriorityBadge={getPriorityBadge} />)
              )}
            </div>
          </section>
        </main>

        {/* Agenda, Workload, Quick Add */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Agenda */}
          <div className="rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-white">
              <h3 className="text-base font-semibold">Адженда на день</h3>
              <button className="h-8 rounded-xl border border-slate-200 px-3 text-sm hover:shadow">
                Синхр. календар
              </button>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-corp-text-main">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Час</th>
                  <th className="px-4 py-2 text-left font-medium">Що</th>
                  <th className="px-4 py-2 text-left font-medium">Хто</th>
                  <th className="px-4 py-2 text-left font-medium">Де</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                <tr className="hover:bg-slate-50/70">
                  <td className="px-4 py-2">10:00</td>
                  <td className="px-4 py-2">Статус-дзвінок</td>
                  <td className="px-4 py-2">менеджери</td>
                  <td className="px-4 py-2">Google Meet</td>
                </tr>
                <tr className="hover:bg-slate-50/70">
                  <td className="px-4 py-2">11:30</td>
                  <td className="px-4 py-2">Видача #6071</td>
                  <td className="px-4 py-2">склад</td>
                  <td className="px-4 py-2">склад</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Workload */}
          <div className="rounded-2xl border border-slate-200 p-4 shadow-sm">
            <h3 className="text-base font-semibold mb-3">Навантаження</h3>
            <ul className="space-y-2 text-sm">
              {[
                { name: 'Вікторія', today: 3, week: 11 },
                { name: 'Богдан', today: 2, week: 9 },
                { name: 'Склад', today: 4, week: 15 },
                { name: 'DevOps', today: 1, week: 3 }
              ].map((r) => (
                <li key={r.name} className="flex items-center gap-3">
                  <div className="w-32 shrink-0">{r.name}</div>
                  <div className="grow h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div className="h-2 bg-teal-500" style={{ width: `${Math.min(100, r.today * 14)}%` }} />
                  </div>
                  <div className="w-16 text-right tabular-nums">{r.today}</div>
                  <div className="w-16 text-right tabular-nums text-corp-text-muted">{r.week}</div>
                </li>
              ))}
            </ul>
            <div className="mt-3 text-xs text-corp-text-muted">* Сьогодні / за тиждень</div>
          </div>

          {/* Quick Add */}
          <div className="rounded-2xl border border-slate-200 p-4 shadow-sm">
            <h3 className="text-base font-semibold mb-3">Швидке створення</h3>
            <div className="grid gap-3">
              <input 
                placeholder="Заголовок" 
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-400"
              />
              <input 
                placeholder="Посилання на замовлення / кейс" 
                className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-400"
              />
              <select className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-400">
                <option>Пріоритет</option>
                <option>low</option>
                <option>medium</option>
                <option>high</option>
                <option>urgent</option>
              </select>
              <select className="rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-400">
                <option>Виконавець</option>
                <option>Вікторія</option>
                <option>Богдан</option>
                <option>Склад</option>
                <option>DevOps</option>
              </select>
            </div>
            <div className="mt-3 flex gap-2">
              <button className="h-9 rounded-xl border border-slate-200 px-3 text-sm hover:shadow">
                Додати тег
              </button>
              <button className="h-9 rounded-xl bg-teal-600 px-3 text-sm text-white hover:bg-teal-700">
                Створити
              </button>
            </div>
          </div>
        </section>
      </div>

      <footer className="border-t border-slate-200 py-6 text-center text-corp-text-muted text-sm">
        © FarforRent • tasks
      </footer>
    </div>
  );
};

// Task Card Component
const TaskCard = ({ task, getPriorityBadge }) => {
  const [bg, tc, label] = getPriorityBadge(task.priority || 'medium');
  
  // Format date to be more readable
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    return date.toLocaleDateString('uk-UA', { 
      day: '2-digit', 
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Truncate long IDs
  const truncateId = (id) => {
    if (!id) return 'T-???';
    if (id.length > 12) {
      return id.substring(0, 8) + '...';
    }
    return id;
  };
  
  return (
    <article className="rounded-2xl border border-slate-200 p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${bg} ${tc}`}>
            {label}
          </span>
          <span className="text-corp-text-muted text-sm" title={task.id}>
            {truncateId(task.id)}
            {task.order_number && ` • #${task.order_number}`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button className="h-8 rounded-xl border border-slate-200 px-3 text-sm hover:shadow">
            Відкрити
          </button>
          <button className="h-8 w-8 rounded-full bg-teal-600 grid place-content-center text-white hover:bg-teal-700" title="Дії">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M8 3V13M3 8H13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      </div>
      <div className="text-sm font-medium mb-3">{task.title || task.description}</div>
      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <div className="text-xs text-corp-text-muted mb-1">Виконавець</div>
          <div className="font-medium truncate">{task.assigned_to || '—'}</div>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <div className="text-xs text-corp-text-muted mb-1">Термін</div>
          <div className="font-medium">{formatDate(task.due_date)}</div>
        </div>
      </div>
      {task.tags && task.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {task.tags.slice(0, 3).map((t, i) => (
            <span key={i} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium">
              {t}
            </span>
          ))}
          {task.tags.length > 3 && (
            <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-corp-text-muted">
              +{task.tags.length - 3}
            </span>
          )}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <button className="h-8 rounded-xl border border-slate-200 px-3 text-xs hover:shadow">
          Перекинути
        </button>
        <button className="h-8 rounded-xl border border-slate-200 px-3 text-xs hover:shadow">
          Коментар
        </button>
        <button className="h-8 rounded-xl border border-slate-200 px-3 text-xs hover:shadow">
          Додати підзадачу
        </button>
      </div>
    </article>
  );
};

export default TasksClean;
