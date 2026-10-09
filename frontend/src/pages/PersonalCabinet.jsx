/* eslint-disable */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import CorporateHeader from '../components/CorporateHeader';
import { User, MessageSquare, CheckSquare, Users, Send, Hash, Lock, Plus, ArrowLeft, Clock, AlertTriangle, Circle, Reply, Search, X, ChevronRight, CalendarDays, Flame, Filter, LayoutGrid, List, Package } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

// Notification sound - короткий "дзінь"
const playNotificationSound = (() => {
  let audioCtx = null;
  return () => {
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, audioCtx.currentTime);
      osc.frequency.setValueAtTime(1174, audioCtx.currentTime + 0.08);
      gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.25);
      osc.start(audioCtx.currentTime);
      osc.stop(audioCtx.currentTime + 0.25);
    } catch {}
  };
})();

const authFetch = (url, opts = {}) => {
  const token = localStorage.getItem('token');
  return fetch(url, { ...opts, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...opts.headers } });
};

const cls = (...a) => a.filter(Boolean).join(' ');

const roleLabels = { admin: 'Адмін', manager: 'Менеджер', requisitor: 'Реквізитор' };
const roleColors = { admin: 'bg-rose-100 text-rose-700', manager: 'bg-sky-100 text-sky-700', requisitor: 'bg-amber-100 text-amber-700' };
const priorityColors = { high: 'bg-rose-500', medium: 'bg-amber-500', low: 'bg-slate-400' };
const priorityLabels = { high: 'Високий', medium: 'Середній', low: 'Низький' };
const statusLabels = { todo: 'До виконання', in_progress: 'В роботі', done: 'Виконано' };
const statusColors = { todo: 'bg-slate-100 text-slate-700', in_progress: 'bg-sky-100 text-sky-700', done: 'bg-emerald-100 text-emerald-700' };
const typeLabels = { packing: 'Комплектація', washing: 'Мийка', restoration: 'Реставрація', reaudit: 'Переоблік', return: 'Повернення', general: 'Загальне', cleaning: 'Мийка', repair: 'Реставрація', delivery: 'Доставка' };
const typeColors = { packing: 'bg-sky-100 text-sky-700', washing: 'bg-sky-100 text-sky-700', cleaning: 'bg-sky-100 text-sky-700', restoration: 'bg-violet-100 text-violet-700', repair: 'bg-violet-100 text-violet-700', reaudit: 'bg-amber-100 text-amber-700', return: 'bg-emerald-100 text-emerald-700', delivery: 'bg-orange-100 text-orange-700', general: 'bg-slate-100 text-slate-700' };

/* ========== PROFILE TAB ========== */
function ProfileTab({ profile, stats }) {
  if (!profile) return <div className="p-8 text-center text-corp-text-muted">Завантаження...</div>;
  return (
    <div className="space-y-5" data-testid="profile-tab">
      <div className="bg-white rounded-xl border border-corp-border p-5">
        <div className="flex items-start gap-5">
          <div className="w-16 h-16 rounded-full bg-corp-primary grid place-content-center text-white text-2xl font-bold flex-shrink-0">
            {(profile.firstname?.[0] || 'U').toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-xl font-semibold text-corp-text-dark">{profile.full_name}</h2>
            <span className={cls('inline-block mt-1 px-2.5 py-0.5 rounded-full text-xs font-medium', roleColors[profile.role] || 'bg-gray-100 text-gray-700')}>
              {roleLabels[profile.role] || profile.role}
            </span>
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-corp-text-main">
              <div><span className="text-corp-text-muted">Email:</span> {profile.email}</div>
              <div><span className="text-corp-text-muted">Логін:</span> {profile.username}</div>
              <div><span className="text-corp-text-muted">Останній вхід:</span> {profile.last_login ? new Date(profile.last_login).toLocaleString('uk-UA') : '—'}</div>
            </div>
          </div>
        </div>
      </div>
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Активних задач" value={(stats.tasks?.todo || 0) + (stats.tasks?.in_progress || 0)} color="text-sky-600" bg="bg-sky-50" />
          <StatCard label="Виконано" value={stats.tasks?.done} color="text-emerald-600" bg="bg-emerald-50" />
          <StatCard label="Прострочених" value={stats.tasks?.overdue} color="text-rose-600" bg="bg-rose-50" />
          <StatCard label="Повідомлень" value={stats.today?.messages_sent} color="text-corp-primary" bg="bg-[#f4f8e6]" />
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, color, bg }) {
  return (
    <div className={cls('rounded-xl p-4 border border-corp-border', bg)}>
      <div className={cls('text-2xl font-bold', color)}>{value || 0}</div>
      <div className="text-xs text-corp-text-muted mt-1">{label}</div>
    </div>
  );
}

/* ========== TASKS TAB (Full Kanban + Focus) ========== */
function TasksTab({ currentUserId }) {
  const [tasks, setTasks] = useState([]);
  const [focus, setFocus] = useState(null);
  const [staff, setStaff] = useState([]);
  const [view, setView] = useState('kanban'); // kanban | list
  const [scope, setScope] = useState('my'); // my | all
  const [filterType, setFilterType] = useState('all');
  const [filterPriority, setFilterPriority] = useState('all');
  const [search, setSearch] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [tasksRes, focusRes, staffRes] = await Promise.all([
        authFetch(`${BACKEND_URL}/api/cabinet/my-tasks?scope=${scope}`),
        authFetch(`${BACKEND_URL}/api/cabinet/focus`),
        authFetch(`${BACKEND_URL}/api/tasks/staff`),
      ]);
      if (tasksRes.ok) setTasks(await tasksRes.json());
      if (focusRes.ok) setFocus(await focusRes.json());
      if (staffRes.ok) setStaff(await staffRes.json());
    } catch (e) { console.error('[Tasks] load error', e); }
    setLoading(false);
  }, [scope]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => tasks.filter(t => {
    if (search && !t.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (filterType !== 'all' && t.task_type !== filterType) return false;
    if (filterPriority !== 'all' && t.priority !== filterPriority) return false;
    return true;
  }), [tasks, search, filterType, filterPriority]);

  const byStatus = useMemo(() => ({
    todo: filtered.filter(t => t.status === 'todo'),
    in_progress: filtered.filter(t => t.status === 'in_progress'),
    done: filtered.filter(t => t.status === 'done'),
  }), [filtered]);

  const changeStatus = async (taskId, newStatus) => {
    await authFetch(`${BACKEND_URL}/api/tasks/${taskId}`, { method: 'PUT', body: JSON.stringify({ status: newStatus }) });
    load();
  };

  const isOverdue = (t) => t.due_date && t.status !== 'done' && new Date(t.due_date) < new Date();

  return (
    <div data-testid="tasks-tab" className="space-y-4">
      {/* Focus of the Day */}
      {focus && (focus.overdue.length > 0 || focus.due_today.length > 0 || focus.in_progress.length > 0) && (
        <div className="bg-white rounded-xl border border-corp-border overflow-hidden" data-testid="focus-widget">
          <div className="px-4 py-3 bg-gradient-to-r from-corp-primary/5 to-transparent border-b border-corp-border">
            <div className="flex items-center gap-2">
              <Flame className="w-4 h-4 text-corp-primary" />
              <span className="text-sm font-semibold text-corp-text-dark">Фокус дня</span>
            </div>
          </div>
          <div className="p-3 space-y-2">
            {focus.overdue.map(t => (
              <FocusItem key={t.id} task={t} tag="Прострочено" tagColor="bg-rose-100 text-rose-700" onClick={() => setSelectedTask(t)} />
            ))}
            {focus.due_today.map(t => (
              <FocusItem key={t.id} task={t} tag="Сьогодні" tagColor="bg-amber-100 text-amber-700" onClick={() => setSelectedTask(t)} />
            ))}
            {focus.in_progress.filter(t => !focus.due_today.find(d => d.id === t.id) && !focus.overdue.find(d => d.id === t.id)).map(t => (
              <FocusItem key={t.id} task={t} tag="В роботі" tagColor="bg-sky-100 text-sky-700" onClick={() => setSelectedTask(t)} />
            ))}
          </div>
          {/* Mini week calendar */}
          {focus.week && (
            <div className="px-3 pb-3">
              <div className="flex gap-1">
                {focus.week.map((d, i) => (
                  <div key={d.date} className={cls('flex-1 text-center rounded-lg py-1.5 text-[10px]',
                    i === 0 ? 'bg-corp-primary/10 border border-corp-primary/30' : 'bg-corp-bg-light border border-corp-border'
                  )}>
                    <div className="text-corp-text-muted">{['Пн','Вт','Ср','Чт','Пт','Сб','Нд'][new Date(d.date).getDay() === 0 ? 6 : new Date(d.date).getDay() - 1]}</div>
                    <div className="font-bold text-corp-text-dark">{new Date(d.date).getDate()}</div>
                    {d.count > 0 && <div className="w-4 h-4 mx-auto rounded-full bg-corp-primary text-white text-[9px] grid place-content-center font-bold">{d.count}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex bg-white rounded-lg border border-corp-border p-0.5">
          {[['my', 'Мої'], ['all', 'Всі']].map(([k, l]) => (
            <button key={k} onClick={() => setScope(k)}
              className={cls('px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                scope === k ? 'bg-corp-primary text-white' : 'text-corp-text-main hover:bg-corp-bg-light'
              )} data-testid={`scope-${k}`}>{l}</button>
          ))}
        </div>
        <div className="flex bg-white rounded-lg border border-corp-border p-0.5">
          <button onClick={() => setView('kanban')} className={cls('p-1.5 rounded-md', view === 'kanban' ? 'bg-corp-primary text-white' : 'text-corp-text-muted')} data-testid="view-kanban">
            <LayoutGrid className="w-4 h-4" />
          </button>
          <button onClick={() => setView('list')} className={cls('p-1.5 rounded-md', view === 'list' ? 'bg-corp-primary text-white' : 'text-corp-text-muted')} data-testid="view-list">
            <List className="w-4 h-4" />
          </button>
        </div>
        <div className="relative flex-1 min-w-[140px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-corp-text-muted" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)} placeholder="Пошук..."
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-corp-border bg-white focus:outline-none focus:border-corp-primary" data-testid="task-search" />
        </div>
        <select value={filterType} onChange={e => setFilterType(e.target.value)}
          className="px-2 py-1.5 text-xs rounded-lg border border-corp-border bg-white text-corp-text-main">
          <option value="all">Всі типи</option>
          {Object.entries(typeLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={filterPriority} onChange={e => setFilterPriority(e.target.value)}
          className="px-2 py-1.5 text-xs rounded-lg border border-corp-border bg-white text-corp-text-main">
          <option value="all">Пріоритет</option>
          {Object.entries(priorityLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-corp-primary text-white text-xs font-medium hover:bg-corp-primary-hover transition-colors" data-testid="create-task-btn">
          <Plus className="w-3.5 h-3.5" /> Задача
        </button>
      </div>

      {/* Stats row */}
      <div className="flex gap-2 text-xs">
        <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600">Всього: <b>{filtered.length}</b></span>
        <span className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600">До: <b>{byStatus.todo.length}</b></span>
        <span className="px-2.5 py-1 rounded-full bg-sky-100 text-sky-600">В роботі: <b>{byStatus.in_progress.length}</b></span>
        <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-600">Зроблено: <b>{byStatus.done.length}</b></span>
      </div>

      {/* Kanban View */}
      {view === 'kanban' ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <KanbanCol title="До виконання" tasks={byStatus.todo} colBg="bg-slate-50" onTaskClick={setSelectedTask} onStatusChange={changeStatus} isOverdue={isOverdue} nextStatus="in_progress" scope={scope} />
          <KanbanCol title="В роботі" tasks={byStatus.in_progress} colBg="bg-sky-50/50" onTaskClick={setSelectedTask} onStatusChange={changeStatus} isOverdue={isOverdue} nextStatus="done" scope={scope} />
          <KanbanCol title="Виконано" tasks={byStatus.done} colBg="bg-emerald-50/50" onTaskClick={setSelectedTask} onStatusChange={changeStatus} isOverdue={() => false} nextStatus="todo" scope={scope} />
        </div>
      ) : (
        <div className="space-y-1.5">
          {filtered.map(t => <TaskRow key={t.id} task={t} isOverdue={isOverdue(t)} onClick={() => setSelectedTask(t)} onStatusChange={changeStatus} scope={scope} />)}
          {filtered.length === 0 && <div className="text-center py-10 text-corp-text-muted text-sm">Немає задач</div>}
        </div>
      )}

      {/* Task Detail */}
      {selectedTask && <TaskDetail task={selectedTask} staff={staff} onClose={() => setSelectedTask(null)} onStatusChange={changeStatus} onRefresh={load} navigate={navigate} />}

      {/* Create Modal */}
      {showCreate && <CreateTaskModal staff={staff} currentUserId={currentUserId} onClose={() => setShowCreate(false)} onSuccess={() => { setShowCreate(false); load(); }} />}
    </div>
  );
}

function FocusItem({ task, tag, tagColor, onClick }) {
  return (
    <button onClick={onClick} className="w-full text-left flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-corp-bg-light transition-colors" data-testid={`focus-${task.id}`}>
      <span className={cls('w-2 h-2 rounded-full flex-shrink-0', priorityColors[task.priority])} />
      <span className="text-sm text-corp-text-dark truncate flex-1">{task.title}</span>
      <span className={cls('px-2 py-0.5 rounded-full text-[10px] font-medium flex-shrink-0', tagColor)}>{tag}</span>
      {task.due_date && <span className="text-[10px] text-corp-text-muted flex-shrink-0">{new Date(task.due_date).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' })}</span>}
    </button>
  );
}

function KanbanCol({ title, tasks, colBg, onTaskClick, onStatusChange, isOverdue, nextStatus, scope }) {
  return (
    <div className={cls('rounded-xl p-3 min-h-[200px]', colBg)}>
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold text-corp-text-dark uppercase tracking-wide">{title}</h4>
        <span className="text-[10px] bg-white/80 px-2 py-0.5 rounded-full text-corp-text-muted font-medium">{tasks.length}</span>
      </div>
      <div className="space-y-2">
        {tasks.map(t => (
          <div key={t.id} onClick={() => onTaskClick(t)}
            className={cls('bg-white rounded-lg border p-2.5 cursor-pointer hover:shadow-sm transition-shadow',
              isOverdue(t) ? 'border-rose-300' : 'border-corp-border'
            )} data-testid={`task-card-${t.id}`}>
            <div className="flex items-start gap-2">
              <button onClick={e => { e.stopPropagation(); onStatusChange(t.id, nextStatus); }} className="mt-0.5 flex-shrink-0">
                <Circle className={cls('w-4 h-4', t.status === 'done' ? 'text-emerald-500 fill-emerald-500' : t.status === 'in_progress' ? 'text-sky-500' : 'text-slate-300')} />
              </button>
              <div className="flex-1 min-w-0">
                <p className={cls('text-xs font-medium', t.status === 'done' ? 'line-through text-corp-text-muted' : 'text-corp-text-dark')}>{t.title}</p>
                <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                  <span className={cls('w-1.5 h-1.5 rounded-full', priorityColors[t.priority])} />
                  {t.task_type && t.task_type !== 'general' && <span className={cls('px-1.5 py-0 rounded text-[9px] font-medium', typeColors[t.task_type])}>{typeLabels[t.task_type]}</span>}
                  {t.due_date && <span className={cls('text-[10px]', isOverdue(t) ? 'text-rose-600 font-medium' : 'text-corp-text-muted')}>{new Date(t.due_date).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' })}</span>}
                  {scope === 'all' && t.assignee_name && <span className="text-[10px] text-corp-text-muted">{t.assignee_name.split(' ')[0]}</span>}
                </div>
                {isOverdue(t) && <span className="inline-block mt-1 px-1.5 py-0 rounded text-[9px] font-medium bg-rose-100 text-rose-700">Прострочено</span>}
              </div>
            </div>
          </div>
        ))}
        {tasks.length === 0 && <div className="text-center text-xs text-corp-text-muted py-6">Порожньо</div>}
      </div>
    </div>
  );
}

function TaskRow({ task, isOverdue, onClick, onStatusChange, scope }) {
  const next = task.status === 'todo' ? 'in_progress' : task.status === 'in_progress' ? 'done' : 'todo';
  return (
    <div onClick={onClick} className={cls('flex items-center gap-3 bg-white rounded-lg border p-2.5 cursor-pointer hover:shadow-sm transition-shadow',
      isOverdue ? 'border-rose-300' : 'border-corp-border'
    )}>
      <button onClick={e => { e.stopPropagation(); onStatusChange(task.id, next); }} className="flex-shrink-0">
        <Circle className={cls('w-4 h-4', task.status === 'done' ? 'text-emerald-500 fill-emerald-500' : task.status === 'in_progress' ? 'text-sky-500' : 'text-slate-300')} />
      </button>
      <span className={cls('w-1.5 h-1.5 rounded-full flex-shrink-0', priorityColors[task.priority])} />
      <span className={cls('text-sm flex-1 truncate', task.status === 'done' ? 'line-through text-corp-text-muted' : 'text-corp-text-dark')}>{task.title}</span>
      {task.task_type && task.task_type !== 'general' && <span className={cls('px-1.5 py-0.5 rounded text-[9px] font-medium hidden sm:inline', typeColors[task.task_type])}>{typeLabels[task.task_type]}</span>}
      <span className={cls('px-1.5 py-0.5 rounded-full text-[9px] font-medium', statusColors[task.status])}>{statusLabels[task.status]}</span>
      {task.due_date && <span className={cls('text-[10px] hidden sm:inline', isOverdue ? 'text-rose-600 font-medium' : 'text-corp-text-muted')}>{new Date(task.due_date).toLocaleDateString('uk-UA')}</span>}
      {scope === 'all' && task.assignee_name && <span className="text-[10px] text-corp-text-muted hidden sm:inline">{task.assignee_name.split(' ')[0]}</span>}
      <ChevronRight className="w-3.5 h-3.5 text-corp-text-muted flex-shrink-0" />
    </div>
  );
}

function TaskDetail({ task, staff, onClose, onStatusChange, onRefresh, navigate }) {
  const [assigneeId, setAssigneeId] = useState(task.assigned_to_id || '');

  const saveAssignee = async () => {
    await authFetch(`${BACKEND_URL}/api/tasks/${task.id}`, { method: 'PUT', body: JSON.stringify({ assigned_to_id: assigneeId ? Number(assigneeId) : null }) });
    onRefresh();
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-t-2xl sm:rounded-xl w-full sm:max-w-lg max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="task-detail">
        <div className="p-5">
          <div className="flex items-start justify-between mb-3">
            <h2 className="text-base font-bold text-corp-text-dark pr-4">{task.title}</h2>
            <button onClick={onClose} className="text-corp-text-muted hover:text-corp-text-dark"><X className="w-5 h-5" /></button>
          </div>
          <div className="flex flex-wrap gap-1.5 mb-3">
            <span className={cls('px-2 py-0.5 rounded-full text-[10px] font-medium', statusColors[task.status])}>{statusLabels[task.status]}</span>
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-600">
              <span className={cls('w-1.5 h-1.5 rounded-full', priorityColors[task.priority])} /> {priorityLabels[task.priority]}
            </span>
            {task.task_type && <span className={cls('px-2 py-0.5 rounded-full text-[10px] font-medium', typeColors[task.task_type])}>{typeLabels[task.task_type]}</span>}
          </div>
          {task.description && <p className="text-sm text-corp-text-main bg-corp-bg-light rounded-lg p-3 mb-3">{task.description}</p>}
          <div className="grid grid-cols-2 gap-2 mb-4 text-sm">
            <div className="p-2.5 bg-corp-bg-light rounded-lg">
              <div className="text-[10px] text-corp-text-muted">Виконавець</div>
              <div className="font-medium text-xs text-corp-text-dark">{task.assignee_name || '—'}</div>
            </div>
            <div className="p-2.5 bg-corp-bg-light rounded-lg">
              <div className="text-[10px] text-corp-text-muted">Дедлайн</div>
              <div className="font-medium text-xs text-corp-text-dark">{task.due_date ? new Date(task.due_date).toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}</div>
            </div>
          </div>
          {task.order_number && (
            <button onClick={() => { navigate(`/order/${task.order_id}/view`); onClose(); }}
              className="mb-3 text-xs text-corp-primary hover:underline font-medium">Замовлення: {task.order_number}</button>
          )}
          {/* Assignee */}
          <div className="mb-4 p-3 bg-corp-bg-light rounded-lg">
            <div className="text-[10px] text-corp-text-muted mb-1.5">Змінити виконавця</div>
            <div className="flex gap-2">
              <select value={assigneeId} onChange={e => setAssigneeId(e.target.value)} className="flex-1 rounded-lg border border-corp-border px-2 py-1.5 text-xs">
                <option value="">Не призначено</option>
                {staff.map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}
              </select>
              <button onClick={saveAssignee} className="px-3 py-1.5 bg-corp-primary text-white rounded-lg text-xs font-medium">OK</button>
            </div>
          </div>
          {/* Status actions */}
          <div className="border-t border-corp-border pt-3">
            <div className="text-[10px] text-corp-text-muted mb-2">Змінити статус:</div>
            <div className="flex flex-wrap gap-2">
              {task.status !== 'todo' && <button onClick={() => { onStatusChange(task.id, 'todo'); onClose(); }} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200">До виконання</button>}
              {task.status !== 'in_progress' && <button onClick={() => { onStatusChange(task.id, 'in_progress'); onClose(); }} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-sky-100 text-sky-700 hover:bg-sky-200">В роботу</button>}
              {task.status !== 'done' && <button onClick={() => { onStatusChange(task.id, 'done'); onClose(); }} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-100 text-emerald-700 hover:bg-emerald-200">Виконано</button>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function CreateTaskModal({ staff, currentUserId, onClose, onSuccess }) {
  const [form, setForm] = useState({
    title: '', description: '', task_type: 'general', priority: 'medium',
    assigned_to_id: currentUserId || '', due_date: '', order_number: '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    const body = {
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      task_type: form.task_type,
      priority: form.priority,
      assigned_to_id: form.assigned_to_id ? Number(form.assigned_to_id) : undefined,
      due_date: form.due_date ? new Date(form.due_date).toISOString() : undefined,
      order_number: form.order_number || undefined,
    };
    const res = await authFetch(`${BACKEND_URL}/api/tasks`, { method: 'POST', body: JSON.stringify(body) });
    if (res.ok) onSuccess();
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-t-2xl sm:rounded-xl w-full sm:max-w-lg max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()} data-testid="create-task-modal">
        <form onSubmit={handleSubmit} className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-corp-text-dark">Нова задача</h2>
            <button type="button" onClick={onClose}><X className="w-5 h-5 text-corp-text-muted" /></button>
          </div>
          <div className="space-y-3">
            <input type="text" required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="Назва задачі *"
              className="w-full px-3 py-2.5 text-sm rounded-lg border border-corp-border focus:outline-none focus:border-corp-primary" data-testid="task-title-input" />
            <textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Опис (необов'язково)" rows={2}
              className="w-full px-3 py-2.5 text-sm rounded-lg border border-corp-border focus:outline-none focus:border-corp-primary resize-none" />
            <div className="grid grid-cols-2 gap-3">
              <select value={form.task_type} onChange={e => setForm({ ...form, task_type: e.target.value })}
                className="px-3 py-2.5 text-sm rounded-lg border border-corp-border">
                <option value="general">Загальне</option>
                <option value="packing">Комплектація</option>
                <option value="washing">Мийка</option>
                <option value="restoration">Реставрація</option>
                <option value="reaudit">Переоблік</option>
                <option value="return">Повернення</option>
                <option value="delivery">Доставка</option>
              </select>
              <select value={form.priority} onChange={e => setForm({ ...form, priority: e.target.value })}
                className="px-3 py-2.5 text-sm rounded-lg border border-corp-border">
                <option value="low">Низький</option>
                <option value="medium">Середній</option>
                <option value="high">Високий</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <select value={form.assigned_to_id} onChange={e => setForm({ ...form, assigned_to_id: e.target.value })}
                className="px-3 py-2.5 text-sm rounded-lg border border-corp-border">
                <option value="">Виконавець</option>
                {staff.map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}
              </select>
              <input type="datetime-local" value={form.due_date} onChange={e => setForm({ ...form, due_date: e.target.value })}
                className="px-3 py-2.5 text-sm rounded-lg border border-corp-border" />
            </div>
            <input type="text" value={form.order_number} onChange={e => setForm({ ...form, order_number: e.target.value })} placeholder="Замовлення (OC-7317)"
              className="w-full px-3 py-2.5 text-sm rounded-lg border border-corp-border focus:outline-none focus:border-corp-primary" />
          </div>
          <div className="flex gap-3 mt-4">
            <button type="submit" className="flex-1 py-2.5 rounded-lg bg-corp-primary text-white text-sm font-medium hover:bg-corp-primary-hover" data-testid="submit-task-btn">Створити</button>
            <button type="button" onClick={onClose} className="px-4 py-2.5 rounded-lg border border-corp-border text-sm text-corp-text-main hover:bg-corp-bg-light">Скасувати</button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ========== CHAT TAB ========== */
function ChatTab({ currentUserId }) {
  const [channels, setChannels] = useState([]);
  const [activeChannel, setActiveChannel] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMsg, setNewMsg] = useState('');
  const [team, setTeam] = useState([]);
  const [thread, setThread] = useState(null);
  const [threadMsgs, setThreadMsgs] = useState([]);
  const [threadReply, setThreadReply] = useState('');
  const [showNewDm, setShowNewDm] = useState(false);
  const [showNewChannel, setShowNewChannel] = useState(false);
  const [newChName, setNewChName] = useState('');
  const [newChDesc, setNewChDesc] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [uploading, setUploading] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  const loadChannels = useCallback(async () => {
    try { const res = await authFetch(`${BACKEND_URL}/api/chat/channels`); if (res.ok) setChannels(await res.json()); } catch {}
  }, []);

  const loadTeam = useCallback(async () => {
    try { const res = await authFetch(`${BACKEND_URL}/api/chat/team`); if (res.ok) setTeam(await res.json()); } catch {}
  }, []);

  const loadMessages = useCallback(async (chId, scroll = false) => {
    if (!chId) return;
    try { const res = await authFetch(`${BACKEND_URL}/api/chat/channels/${chId}/messages`); if (res.ok) { setMessages(await res.json()); } } catch {}
  }, []);

  useEffect(() => { loadChannels(); loadTeam(); }, [loadChannels, loadTeam]);

  useEffect(() => {
    if (!activeChannel) return;
    loadMessages(activeChannel.id, true);
    pollRef.current = setInterval(() => { loadMessages(activeChannel.id, false); loadChannels(); }, 5000);
    return () => clearInterval(pollRef.current);
  }, [activeChannel, loadMessages, loadChannels]);

  const sendMessage = async () => {
    if (!newMsg.trim() || !activeChannel) return;
    await authFetch(`${BACKEND_URL}/api/chat/channels/${activeChannel.id}/messages`, { method: 'POST', body: JSON.stringify({ message: newMsg.trim() }) });
    setNewMsg(''); loadMessages(activeChannel.id, true); loadChannels();
  };

  const sendThreadReply = async () => {
    if (!threadReply.trim() || !thread || !activeChannel || thread.is_closed) return;
    await authFetch(`${BACKEND_URL}/api/chat/channels/${activeChannel.id}/messages`, { method: 'POST', body: JSON.stringify({ message: threadReply.trim(), reply_to: thread.id }) });
    setThreadReply('');
    const res = await authFetch(`${BACKEND_URL}/api/chat/messages/${thread.id}/thread`);
    if (res.ok) setThreadMsgs(await res.json());
    loadMessages(activeChannel.id);
  };

  const openThread = async (msg) => {
    setThread(msg);
    const res = await authFetch(`${BACKEND_URL}/api/chat/messages/${msg.id}/thread`);
    if (res.ok) setThreadMsgs(await res.json());
  };

  const toggleCloseThread = async () => {
    if (!thread) return;
    const action = thread.is_closed ? 'reopen' : 'close';
    const r = await authFetch(`${BACKEND_URL}/api/chat/messages/${thread.id}/${action}`, { method: 'PUT' });
    if (r.ok) {
      const d = await r.json();
      setThread({ ...thread, is_closed: d.is_closed });
      loadMessages(activeChannel.id);
    }
  };
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !activeChannel) return;
    setUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('channel_id', activeChannel.id);
    fd.append('message', '');
    const token = localStorage.getItem('token');
    try {
      const r = await fetch(`${BACKEND_URL}/api/chat/upload`, { method: 'POST', body: fd, headers: { Authorization: `Bearer ${token}` } });
      if (r.ok) { loadMessages(activeChannel.id); loadChannels(); }
    } catch {}
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };
  const createDm = async (userId) => {
    const res = await authFetch(`${BACKEND_URL}/api/chat/dm/${userId}`, { method: 'POST' });
    if (res.ok) { const dm = await res.json(); setShowNewDm(false); loadChannels(); setActiveChannel(dm); }
  };

  const createChannel = async () => {
    if (!newChName.trim()) return;
    const res = await authFetch(`${BACKEND_URL}/api/chat/channels`, { method: 'POST', body: JSON.stringify({ name: newChName.trim(), description: newChDesc.trim(), type: 'topic' }) });
    if (res.ok) { setShowNewChannel(false); setNewChName(''); setNewChDesc(''); loadChannels(); }
  };

  const filteredChannels = channels.filter(c => !searchQuery || c.name.toLowerCase().includes(searchQuery.toLowerCase()));
  const channelIcon = (type) => type === 'dm' ? <Lock className="w-4 h-4 text-corp-text-muted" /> : <Hash className="w-4 h-4 text-corp-text-muted" />;
  const PaperclipIcon = ({ className }) => <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>;
  const LockClosed = ({ className }) => <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>;
  const LockOpen = ({ className }) => <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>;

  return (
    <div className="flex h-[calc(100dvh-140px)] sm:h-[calc(100vh-200px)] bg-white rounded-xl border border-corp-border overflow-hidden" data-testid="chat-tab">
      {/* Sidebar */}
      <div className={cls('flex-shrink-0 border-r border-corp-border flex flex-col bg-corp-bg-light', activeChannel ? 'hidden sm:flex w-72' : 'w-full sm:w-72')}>
        <div className="p-3 space-y-2 border-b border-corp-border">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-corp-text-muted" />
            <input type="text" placeholder="Пошук..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-corp-border bg-white focus:outline-none focus:border-corp-primary" data-testid="chat-search" />
          </div>
          <div className="flex gap-1.5">
            <button onClick={() => setShowNewChannel(true)} className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs rounded-lg bg-corp-primary text-white hover:bg-corp-primary-hover transition-colors" data-testid="new-channel-btn">
              <Plus className="w-3.5 h-3.5" /> Канал
            </button>
            <button onClick={() => setShowNewDm(true)} className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-xs rounded-lg bg-corp-gold text-white hover:bg-corp-gold-hover transition-colors" data-testid="new-dm-btn">
              <Plus className="w-3.5 h-3.5" /> Особисте
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {filteredChannels.map(ch => (
            <button key={ch.id} onClick={() => { setActiveChannel(ch); setThread(null); }}
              className={cls('w-full text-left px-3 py-2.5 flex items-center gap-2.5 hover:bg-white/80 transition-colors border-b border-corp-border/50',
                activeChannel?.id === ch.id && 'bg-white shadow-sm')} data-testid={`channel-${ch.id}`}>
              {channelIcon(ch.type)}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-corp-text-dark truncate">{ch.name}</span>
                  {ch.unread > 0 && <span className="ml-1 w-5 h-5 rounded-full bg-corp-primary text-white text-[10px] grid place-content-center font-bold flex-shrink-0">{ch.unread}</span>}
                </div>
                {ch.last_message && <p className="text-[11px] text-corp-text-muted truncate mt-0.5"><span className="font-medium">{ch.last_message.user_name?.split(' ')[0]}:</span> {ch.last_message.text}</p>}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Main Chat */}
      <div className={cls('flex-1 flex flex-col', !activeChannel && 'hidden sm:flex')}>
        {activeChannel ? (
          <>
            <div className="px-4 py-3 border-b border-corp-border flex items-center gap-3 bg-white">
              <button onClick={() => setActiveChannel(null)} className="sm:hidden"><ArrowLeft className="w-5 h-5 text-corp-text-main" /></button>
              {channelIcon(activeChannel.type)}
              <div>
                <div className="text-sm font-semibold text-corp-text-dark">{activeChannel.name}</div>
                {activeChannel.description && <div className="text-[11px] text-corp-text-muted">{activeChannel.description}</div>}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-corp-bg-light/50">
              {messages.map(msg => (
                <div key={msg.id} className={cls('flex gap-2.5', msg.user_id === currentUserId && 'flex-row-reverse')} data-testid={`message-${msg.id}`}>
                  <div className={cls('w-8 h-8 rounded-full grid place-content-center text-xs font-bold flex-shrink-0', msg.user_id === currentUserId ? 'bg-corp-primary text-white' : 'bg-corp-gold text-white')}>
                    {(msg.user_name?.[0] || 'U').toUpperCase()}
                  </div>
                  <div className={cls('max-w-[75%] rounded-xl px-3 py-2',
                    msg.task_id ? 'bg-amber-50 border border-amber-200 rounded-tl-sm' :
                    msg.user_id === currentUserId ? 'bg-corp-primary/10 rounded-tr-sm' : 'bg-white border border-corp-border rounded-tl-sm'
                  )}>
                    <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                      <span className="text-xs font-semibold text-corp-text-dark">{msg.user_name}</span>
                      <span className={cls('px-1.5 py-0 rounded text-[9px] font-medium', roleColors[msg.user_role])}>{roleLabels[msg.user_role] || msg.user_role}</span>
                      <span className="text-[10px] text-corp-text-muted">{msg.created_at ? new Date(msg.created_at).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                      {msg.task_id && <span className="px-1.5 py-0 rounded text-[9px] font-medium bg-amber-100 text-amber-700">Задача</span>}
                      {msg.is_closed && <span className="px-1.5 py-0 rounded text-[9px] font-medium bg-slate-200 text-slate-600">Закрито</span>}
                    </div>
                    <p className="text-sm text-corp-text-dark whitespace-pre-wrap break-words">{msg.message}</p>
                    {msg.attachment_url && msg.attachment_type === 'image' && (
                      <a href={`${BACKEND_URL}${msg.attachment_url}`} target="_blank" rel="noopener noreferrer">
                        <img src={`${BACKEND_URL}${msg.attachment_url}`} alt="" className="mt-2 rounded-lg max-w-[240px] max-h-[180px] object-cover border border-corp-border cursor-pointer hover:opacity-90 transition-opacity" data-testid={`img-${msg.id}`} />
                      </a>
                    )}
                    <button onClick={() => openThread(msg)} className="flex items-center gap-1 mt-1 text-[10px] text-corp-text-muted hover:text-corp-primary transition-colors" data-testid={`thread-btn-${msg.id}`}>
                      <Reply className="w-3 h-3" /> {msg.thread_count > 0 ? `${msg.thread_count} відповідей` : 'Відповісти'}
                    </button>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <div className="p-3 border-t border-corp-border bg-white">
              <div className="flex items-center gap-2">
                <input type="file" ref={fileInputRef} className="hidden" accept="image/*" onChange={handleFileUpload} data-testid="file-input" />
                <button onClick={() => fileInputRef.current?.click()} className={cls('p-2.5 rounded-xl border border-corp-border text-corp-text-muted hover:text-corp-primary hover:border-corp-primary transition-colors', uploading && 'animate-pulse')} data-testid="attach-btn" disabled={uploading}>
                  <PaperclipIcon className="w-5 h-5" />
                </button>
                <input type="text" value={newMsg} onChange={e => setNewMsg(e.target.value)} onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendMessage())}
                  placeholder="Написати повідомлення..." className="flex-1 px-4 py-2.5 text-sm rounded-xl border border-corp-border bg-corp-bg-light focus:outline-none focus:border-corp-primary focus:bg-white transition-colors" data-testid="chat-input" />
                <button onClick={sendMessage} className="p-2.5 rounded-xl bg-corp-primary text-white hover:bg-corp-primary-hover transition-colors disabled:opacity-50" disabled={!newMsg.trim()} data-testid="chat-send-btn">
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 grid place-content-center text-corp-text-muted text-sm">
            <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>Оберіть канал для спілкування</p>
          </div>
        )}
      </div>

      {/* Thread Panel */}
      {thread && (
        <div className="w-80 border-l border-corp-border flex flex-col bg-white hidden lg:flex">
          <div className="px-4 py-3 border-b border-corp-border flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-corp-text-dark">Тред</span>
              {thread.is_closed && <span className="px-1.5 py-0 rounded text-[9px] font-medium bg-slate-200 text-slate-600">Закрито</span>}
            </div>
            <div className="flex items-center gap-1">
              <button onClick={toggleCloseThread} className="p-1 hover:bg-corp-bg-light rounded" title={thread.is_closed ? 'Відкрити тред' : 'Закрити тред'} data-testid="toggle-close-thread">
                {thread.is_closed ? <LockOpen className="w-4 h-4 text-emerald-500" /> : <LockClosed className="w-4 h-4 text-corp-text-muted" />}
              </button>
              <button onClick={() => setThread(null)} className="p-1 hover:bg-corp-bg-light rounded"><X className="w-4 h-4 text-corp-text-muted" /></button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {threadMsgs.map(msg => (
              <div key={msg.id} className={cls('rounded-lg px-3 py-2', msg.is_parent ? 'bg-corp-bg-light border border-corp-border' : 'bg-white border border-corp-border/50')}>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-semibold text-corp-text-dark">{msg.user_name}</span>
                  <span className="text-[10px] text-corp-text-muted">{msg.created_at ? new Date(msg.created_at).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                </div>
                <p className="text-sm text-corp-text-dark">{msg.message}</p>
                {msg.attachment_url && msg.attachment_type === 'image' && (
                  <a href={`${BACKEND_URL}${msg.attachment_url}`} target="_blank" rel="noopener noreferrer">
                    <img src={`${BACKEND_URL}${msg.attachment_url}`} alt="" className="mt-1 rounded-lg max-w-full max-h-[120px] object-cover" />
                  </a>
                )}
              </div>
            ))}
          </div>
          {!thread.is_closed ? (
          <div className="p-3 border-t border-corp-border">
            <div className="flex items-center gap-2">
              <input type="text" value={threadReply} onChange={e => setThreadReply(e.target.value)} onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendThreadReply())}
                placeholder="Відповісти в тред..." className="flex-1 px-3 py-2 text-sm rounded-lg border border-corp-border focus:outline-none focus:border-corp-primary" data-testid="thread-input" />
              <button onClick={sendThreadReply} className="p-2 rounded-lg bg-corp-primary text-white hover:bg-corp-primary-hover disabled:opacity-50" disabled={!threadReply.trim()}>
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
          ) : (
            <div className="p-3 border-t border-corp-border text-center text-xs text-corp-text-muted">Тред закрито. Натисніть замок, щоб відкрити.</div>
          )}
        </div>
      )}

      {/* New Channel Modal */}
      {showNewChannel && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowNewChannel(false)}>
          <div className="bg-white rounded-xl p-5 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()} data-testid="new-channel-modal">
            <h3 className="text-base font-semibold text-corp-text-dark mb-4">Новий канал</h3>
            <input type="text" value={newChName} onChange={e => setNewChName(e.target.value)} placeholder="Назва каналу"
              className="w-full px-3 py-2.5 text-sm rounded-lg border border-corp-border mb-3 focus:outline-none focus:border-corp-primary" data-testid="new-channel-name" />
            <input type="text" value={newChDesc} onChange={e => setNewChDesc(e.target.value)} placeholder="Опис (необов'язково)"
              className="w-full px-3 py-2.5 text-sm rounded-lg border border-corp-border mb-4 focus:outline-none focus:border-corp-primary" />
            <div className="flex gap-2">
              <button onClick={() => setShowNewChannel(false)} className="flex-1 px-3 py-2 text-sm rounded-lg border border-corp-border text-corp-text-main hover:bg-corp-bg-light">Скасувати</button>
              <button onClick={createChannel} className="flex-1 px-3 py-2 text-sm rounded-lg bg-corp-primary text-white hover:bg-corp-primary-hover" data-testid="create-channel-btn">Створити</button>
            </div>
          </div>
        </div>
      )}

      {/* New DM Modal */}
      {showNewDm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowNewDm(false)}>
          <div className="bg-white rounded-xl p-5 w-full max-w-sm shadow-xl" onClick={e => e.stopPropagation()} data-testid="new-dm-modal">
            <h3 className="text-base font-semibold text-corp-text-dark mb-4">Особисте повідомлення</h3>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {team.filter(m => m.id !== currentUserId).map(m => (
                <button key={m.id} onClick={() => createDm(m.id)}
                  className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-corp-bg-light flex items-center gap-3 transition-colors" data-testid={`dm-user-${m.id}`}>
                  <div className="w-8 h-8 rounded-full bg-corp-gold grid place-content-center text-white text-xs font-bold">{(m.name?.[0] || 'U').toUpperCase()}</div>
                  <div>
                    <div className="text-sm font-medium text-corp-text-dark">{m.name}</div>
                    <div className="text-[11px] text-corp-text-muted">{roleLabels[m.role] || m.role}</div>
                  </div>
                </button>
              ))}
            </div>
            <button onClick={() => setShowNewDm(false)} className="mt-3 w-full px-3 py-2 text-sm rounded-lg border border-corp-border text-corp-text-main hover:bg-corp-bg-light">Скасувати</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ========== ORDER CHATS TAB ========== */
const orderStatusConfig = {
  awaiting_customer: { label: 'Очікує', color: 'bg-amber-500' },
  processing: { label: 'Комплектація', color: 'bg-blue-500' },
  ready_for_issue: { label: 'Готово', color: 'bg-emerald-500' },
  issued: { label: 'Видано', color: 'bg-purple-500' },
  on_rent: { label: 'В оренді', color: 'bg-indigo-500' },
  partial_return: { label: 'Часткове', color: 'bg-orange-500' },
  returned: { label: 'Повернено', color: 'bg-slate-500' },
  completed: { label: 'Завершено', color: 'bg-slate-400' },
  cancelled: { label: 'Скасовано', color: 'bg-red-400' },
};

function OrderChatsTab() {
  const [orders, setOrders] = useState([]);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [sending, setSending] = useState(false);
  const [filterMode, setFilterMode] = useState('active');
  const [searchQuery, setSearchQuery] = useState('');
  const messagesEndRef = useRef(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ mode: filterMode });
      if (searchQuery.trim()) params.set('search', searchQuery.trim());
      const r = await authFetch(`${BACKEND_URL}/api/cabinet/order-chats?${params}`);
      if (r.ok) setOrders(await r.json());
    } catch (e) { console.error('[OrderChats] load error', e); }
    setLoading(false);
  }, [filterMode, searchQuery]);

  useEffect(() => { loadOrders(); }, [loadOrders]);

  const loadMessages = useCallback(async (orderId) => {
    setLoadingMsgs(true);
    try {
      const r = await authFetch(`${BACKEND_URL}/api/orders/${orderId}/internal-notes`);
      if (r.ok) { const d = await r.json(); setMessages(d.notes || []); }
    } catch (e) { console.error('[OrderChats] messages error', e); }
    setLoadingMsgs(false);
  }, []);

  useEffect(() => {
    if (selectedOrder) {
      loadMessages(selectedOrder.order_id);
    }
  }, [selectedOrder, loadMessages]);

  // Auto-scroll removed — only scroll after sending

  const sendMessage = async () => {
    if (!newMessage.trim() || !selectedOrder || sending) return;
    setSending(true);
    try {
      const r = await authFetch(`${BACKEND_URL}/api/orders/${selectedOrder.order_id}/internal-notes`, {
        method: 'POST', body: JSON.stringify({ message: newMessage.trim() })
      });
      if (r.ok) {
        setNewMessage('');
        loadMessages(selectedOrder.order_id);
        loadOrders();
      }
    } catch (e) { console.error('[OrderChats] send error', e); }
    setSending(false);
  };

  const selectOrder = (order) => {
    setSelectedOrder(order);
  };

  const getUserColor = (name) => {
    const colors = [
      'bg-blue-50 border-blue-200', 'bg-emerald-50 border-emerald-200',
      'bg-violet-50 border-violet-200', 'bg-amber-50 border-amber-200',
      'bg-rose-50 border-rose-200', 'bg-cyan-50 border-cyan-200',
    ];
    const hash = (name || '').split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
    return colors[hash % colors.length];
  };

  const filteredOrders = orders;

  return (
    <div className="flex h-[calc(100dvh-140px)] sm:h-[calc(100vh-200px)] bg-white rounded-xl border border-corp-border overflow-hidden" data-testid="order-chats-tab">
      {/* Left sidebar — orders list */}
      <div className={cls('flex-shrink-0 border-r border-corp-border flex flex-col bg-corp-bg-light',
        selectedOrder ? 'hidden sm:flex w-72 lg:w-80' : 'w-full sm:w-72 lg:w-80')}>
        {/* Search & filters */}
        <div className="p-3 space-y-2 border-b border-corp-border">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-corp-text-muted" />
            <input type="text" placeholder="Пошук замовлення..." value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-2 text-sm rounded-lg border border-corp-border bg-white focus:outline-none focus:border-corp-primary"
              data-testid="order-chat-search" />
          </div>
          <div className="flex gap-1 bg-white rounded-lg border border-corp-border p-0.5">
            {[['active', 'Активні'], ['with_notes', 'З нотатками'], ['all', 'Всі']].map(([k, l]) => (
              <button key={k} onClick={() => setFilterMode(k)}
                className={cls('flex-1 px-2 py-1.5 rounded-md text-[11px] font-medium transition-colors',
                  filterMode === k ? 'bg-corp-primary text-white' : 'text-corp-text-main hover:bg-corp-bg-light'
                )} data-testid={`order-filter-${k}`}>{l}</button>
            ))}
          </div>
        </div>

        {/* Orders List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-sm text-corp-text-muted animate-pulse">Завантаження...</div>
          ) : filteredOrders.length === 0 ? (
            <div className="p-6 text-center">
              <Package className="w-10 h-10 mx-auto mb-2 text-corp-text-muted opacity-30" />
              <p className="text-sm text-corp-text-muted">Немає замовлень</p>
            </div>
          ) : (
            filteredOrders.map(order => {
              const st = orderStatusConfig[order.status] || { label: order.status, color: 'bg-slate-400' };
              const isSelected = selectedOrder?.order_id === order.order_id;
              return (
                <button key={order.order_id} onClick={() => selectOrder(order)}
                  className={cls('w-full text-left px-3 py-2.5 border-b border-corp-border/50 transition-colors',
                    isSelected ? 'bg-white shadow-sm' : 'hover:bg-white/80'
                  )} data-testid={`order-item-${order.order_id}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <div className={cls('w-2 h-2 rounded-full flex-shrink-0', st.color)} />
                    <span className={cls('text-sm font-semibold', isSelected ? 'text-corp-primary' : 'text-corp-text-dark')}>
                      {order.order_number}
                    </span>
                    <span className="text-[9px] text-corp-text-muted bg-corp-bg-light px-1.5 py-0.5 rounded">{st.label}</span>
                    {order.notes_count > 0 && (
                      <span className="ml-auto w-5 h-5 rounded-full bg-corp-primary/10 text-corp-primary text-[10px] grid place-content-center font-bold flex-shrink-0">
                        {order.notes_count}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-corp-text-muted truncate">{order.customer_name}</div>
                  {order.last_note_text && (
                    <div className="text-[11px] text-corp-text-muted mt-1 truncate">
                      <span className="font-medium">{order.last_note_user?.split(' ')[0]}:</span> {order.last_note_text}
                    </div>
                  )}
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Right panel — Chat */}
      <div className={cls('flex-1 flex flex-col', !selectedOrder && 'hidden sm:flex')}>
        {selectedOrder ? (
          <>
            {/* Chat header */}
            <div className="px-4 py-3 border-b border-corp-border flex items-center gap-3 bg-white">
              <button onClick={() => setSelectedOrder(null)} className="sm:hidden">
                <ArrowLeft className="w-5 h-5 text-corp-text-main" />
              </button>
              <div className={cls('w-2.5 h-2.5 rounded-full flex-shrink-0', (orderStatusConfig[selectedOrder.status] || {}).color || 'bg-slate-400')} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-corp-text-dark">{selectedOrder.order_number}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-corp-bg-light text-corp-text-muted">
                    {(orderStatusConfig[selectedOrder.status] || {}).label || selectedOrder.status}
                  </span>
                </div>
                <div className="text-xs text-corp-text-muted truncate">{selectedOrder.customer_name}</div>
              </div>
              {(selectedOrder.issue_date || selectedOrder.return_date) && (
                <div className="hidden md:flex items-center gap-3 text-[11px] text-corp-text-muted">
                  {selectedOrder.issue_date && <span>Видача: {new Date(selectedOrder.issue_date).toLocaleDateString('uk-UA')}</span>}
                  {selectedOrder.return_date && <span>Повернення: {new Date(selectedOrder.return_date).toLocaleDateString('uk-UA')}</span>}
                </div>
              )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-corp-bg-light/50">
              {loadingMsgs ? (
                <div className="text-center text-corp-text-muted py-8 text-sm animate-pulse">Завантаження...</div>
              ) : messages.length === 0 ? (
                <div className="text-center text-corp-text-muted py-12">
                  <MessageSquare className="w-12 h-12 mx-auto mb-3 opacity-20" />
                  <p className="text-sm">Немає повідомлень</p>
                  <p className="text-xs mt-1 text-corp-text-muted">Напишіть перше повідомлення</p>
                </div>
              ) : (
                messages.map((msg) => {
                  const isClient = msg.user_name?.includes('Коментар клієнта');
                  const isSystem = msg.user_name === 'System';
                  return (
                    <div key={msg.id} className={cls('max-w-[85%]', !isClient && !isSystem && 'ml-auto')} data-testid={`order-msg-${msg.id}`}>
                      <div className={cls('rounded-xl border px-3 py-2.5', getUserColor(msg.user_name),
                        isClient ? 'bg-amber-50 border-amber-200' :
                        isSystem ? 'bg-white border-corp-border' : ''
                      )}>
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-xs font-semibold text-corp-text-dark">{msg.user_name || 'Невідомий'}</span>
                          <span className="text-[10px] text-corp-text-muted flex-shrink-0">{msg.created_at}</span>
                        </div>
                        <p className="text-sm text-corp-text-dark whitespace-pre-wrap break-words">{msg.message}</p>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="p-3 border-t border-corp-border bg-white">
              <div className="flex items-center gap-2">
                <input type="text" value={newMessage}
                  onChange={e => setNewMessage(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendMessage())}
                  placeholder="Нотатка для команди..."
                  className="flex-1 px-4 py-2.5 text-sm rounded-xl border border-corp-border bg-corp-bg-light focus:outline-none focus:border-corp-primary focus:bg-white transition-colors"
                  data-testid="order-chat-input" />
                <button onClick={sendMessage}
                  className="p-2.5 rounded-xl bg-corp-primary text-white hover:bg-corp-primary-hover transition-colors disabled:opacity-50"
                  disabled={!newMessage.trim() || sending} data-testid="order-chat-send">
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 grid place-content-center text-corp-text-muted text-sm">
            <Package className="w-12 h-12 mx-auto mb-3 opacity-20" />
            <p>Оберіть замовлення для перегляду чату</p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ========== TEAM TAB ========== */
function TeamTab({ teamData }) {
  if (!teamData?.length) return <div className="p-8 text-center text-corp-text-muted">Завантаження...</div>;
  return (
    <div className="space-y-2" data-testid="team-tab">
      {teamData.map(m => (
        <div key={m.user_id} className="bg-white rounded-lg border border-corp-border p-4 flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-corp-gold grid place-content-center text-white font-bold flex-shrink-0">{(m.name?.[0] || 'U').toUpperCase()}</div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-corp-text-dark">{m.name}</span>
              <span className={cls('px-2 py-0.5 rounded-full text-[10px] font-medium', roleColors[m.role])}>{roleLabels[m.role]}</span>
            </div>
            <div className="flex items-center gap-4 mt-1 text-xs text-corp-text-muted">
              <span>Активних: <b className="text-corp-text-dark">{m.active_tasks}</b></span>
              <span>Сьогодні: <b className="text-emerald-600">{m.done_today}</b></span>
              {m.last_login && <span>Вхід: {new Date(m.last_login).toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ========== MAIN PAGE ========== */
export default function PersonalCabinet() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'profile');
  const [profile, setProfile] = useState(null);
  const [stats, setStats] = useState(null);
  const [teamData, setTeamData] = useState([]);
  const [unread, setUnread] = useState(0);
  const [orderNotesNew, setOrderNotesNew] = useState(0);
  const navigate = useNavigate();
  const prevUnreadRef = useRef(0);
  const prevOrderNotesRef = useRef(0);
  const activeTabRef = useRef(activeTab);

  // Тримаємо актуальну вкладку в ref для доступу з polling
  useEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);

  const currentUserId = (() => {
    try { const u = JSON.parse(localStorage.getItem('user') || '{}'); return u.user_id || u.id; } catch { return null; }
  })();

  useEffect(() => {
    const loadData = async () => {
      try {
        const [pRes, sRes, tRes, uRes, onRes] = await Promise.all([
          authFetch(`${BACKEND_URL}/api/cabinet/profile`),
          authFetch(`${BACKEND_URL}/api/cabinet/stats`),
          authFetch(`${BACKEND_URL}/api/cabinet/team`),
          authFetch(`${BACKEND_URL}/api/chat/unread`),
          authFetch(`${BACKEND_URL}/api/cabinet/order-notes-new`),
        ]);
        if (pRes.ok) setProfile(await pRes.json());
        if (sRes.ok) setStats(await sRes.json());
        if (tRes.ok) setTeamData(await tRes.json());
        if (uRes.ok) { const d = await uRes.json(); setUnread(d.unread || 0); }
        if (onRes.ok) { const d = await onRes.json(); setOrderNotesNew(d.count || 0); }
      } catch (e) { console.error('[Cabinet] init error', e); }
    };
    loadData();
    const interval = setInterval(async () => {
      try {
        const [r, on] = await Promise.all([
          authFetch(`${BACKEND_URL}/api/chat/unread`),
          authFetch(`${BACKEND_URL}/api/cabinet/order-notes-new`),
        ]);
        if (r.ok) {
          const d = await r.json();
          const newUnread = d.unread || 0;
          // Звук тільки якщо не в чаті і є нові повідомлення
          if (newUnread > prevUnreadRef.current && activeTabRef.current !== 'chat') {
            playNotificationSound();
          }
          prevUnreadRef.current = newUnread;
          // Якщо в чаті — показуємо 0 (повідомлення вже прочитані)
          setUnread(activeTabRef.current === 'chat' ? 0 : newUnread);
        }
        if (on.ok) {
          const d = await on.json();
          const newNotes = d.count || 0;
          if (newNotes > prevOrderNotesRef.current && activeTabRef.current !== 'orders') {
            playNotificationSound();
          }
          prevOrderNotesRef.current = newNotes;
          setOrderNotesNew(activeTabRef.current === 'orders' ? 0 : newNotes);
        }
      } catch {}
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const switchTab = (tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
    // Скидаємо лічильник при вході в чат/замовлення
    if (tab === 'chat') setUnread(0);
    if (tab === 'orders') setOrderNotesNew(0);
  };

  const tabs = [
    { key: 'profile', label: 'Профіль', icon: User },
    { key: 'tasks', label: 'Задачі', icon: CheckSquare },
    { key: 'chat', label: 'Чат', icon: MessageSquare, count: unread },
    { key: 'orders', label: 'Замовлення', icon: Package, count: orderNotesNew },
    { key: 'team', label: 'Команда', icon: Users },
  ];

  return (
    <div className="min-h-screen bg-corp-bg-page" data-testid="personal-cabinet">
      <CorporateHeader cabinetName="Особистий кабінет" showBackButton />
      <div className="mx-auto max-w-6xl px-2 sm:px-6 py-2 sm:py-4">
        <div className="flex gap-1 mb-2 sm:mb-5 bg-white rounded-xl p-1.5 border border-corp-border overflow-x-auto" data-testid="cabinet-tabs">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button key={tab.key} onClick={() => switchTab(tab.key)}
                className={cls('flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap',
                  activeTab === tab.key ? 'bg-corp-primary text-white shadow-sm' : 'text-corp-text-main hover:bg-corp-bg-light'
                )} data-testid={`tab-${tab.key}`}>
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{tab.label}</span>
                {tab.count > 0 && (
                  <span className={cls('w-5 h-5 rounded-full text-[10px] grid place-content-center font-bold',
                    activeTab === tab.key ? 'bg-white text-corp-primary' : 'bg-corp-primary text-white'
                  )}>{tab.count > 99 ? '99+' : tab.count}</span>
                )}
              </button>
            );
          })}
        </div>
        {activeTab === 'profile' && <ProfileTab profile={profile} stats={stats} />}
        {activeTab === 'tasks' && <TasksTab currentUserId={currentUserId} />}
        {activeTab === 'chat' && <ChatTab currentUserId={currentUserId} />}
        {activeTab === 'orders' && <OrderChatsTab />}
        {activeTab === 'team' && <TeamTab teamData={teamData} />}
      </div>
    </div>
  );
}
