import { $, $$ } from '../utils/domHelpers.js';
import { fmtDateFull } from '../utils/formatters.js';

const MONTHS = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
const DOW_LABELS = ['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];
const ALL_SLOTS = ['10:00','11:00','12:00','13:00','14:00','15:00','16:00','17:00','18:00','19:00'];

const CLOSED_DAYS = new Set([0, 1]); // Sunday, Monday

/** Computed fresh each render so midnight rollovers are handled correctly. */
function getToday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function currentMonthStart() {
  const d = new Date();
  d.setDate(1);
  d.setHours(0, 0, 0, 0);
  return d;
}

/** Internal calendar state. */
const state = {
  cursor: currentMonthStart(),
  date: /** @type {Date|null} */ (null),
  time: /** @type {string|null} */ (null),
};

/** @type {(() => void)|null} */
let onChangeCallback = null;

/**
 * Initialize the calendar and time-slot picker.
 * @param {() => void} onChange - called when date or time selection changes
 */
export function initCalendar(onChange) {
  onChangeCallback = onChange;
  renderCalendar();
  renderSlots();

  $('#prevMonth').addEventListener('click', () => {
    const prev = new Date(state.cursor.getFullYear(), state.cursor.getMonth() - 1, 1);
    // Do not navigate before the current month
    if (prev >= currentMonthStart()) {
      state.cursor = prev;
      renderCalendar();
    }
  });

  $('#nextMonth').addEventListener('click', () => {
    state.cursor = new Date(state.cursor.getFullYear(), state.cursor.getMonth() + 1, 1);
    renderCalendar();
  });
}

/**
 * Return the currently selected date, or null.
 * @returns {Date|null}
 */
export const getSelectedDate = () => state.date;

/**
 * Return the currently selected time string (e.g. "14:00"), or null.
 * @returns {string|null}
 */
export const getSelectedTime = () => state.time;

/**
 * Reset date, time, and calendar cursor back to the current month.
 */
export function resetCalendar() {
  state.date = null;
  state.time = null;
  state.cursor = currentMonthStart();
  renderCalendar();
  renderSlots();
}

// ---------- private ----------

function sameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function renderCalendar() {
  const today = getToday();
  const { cursor } = state;

  $('#calMonth').textContent = `${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}`;

  // Disable "prev" button if already at current month
  const prevBtn = $('#prevMonth');
  const isCurrentMonth =
    cursor.getFullYear() === today.getFullYear() &&
    cursor.getMonth() === today.getMonth();
  prevBtn.disabled = isCurrentMonth;
  prevBtn.setAttribute('aria-disabled', String(isCurrentMonth));

  const grid = $('#calGrid');
  grid.innerHTML = '';

  DOW_LABELS.forEach((label) => {
    const el = document.createElement('div');
    el.className = 'calendar__dow';
    el.textContent = label;
    el.setAttribute('aria-hidden', 'true');
    grid.appendChild(el);
  });

  const firstDow = new Date(cursor.getFullYear(), cursor.getMonth(), 1).getDay();
  const daysInMonth = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate();

  for (let i = 0; i < firstDow; i++) {
    const blank = document.createElement('div');
    blank.className = 'calendar__day calendar__day--empty';
    blank.setAttribute('aria-hidden', 'true');
    grid.appendChild(blank);
  }

  for (let d = 1; d <= daysInMonth; d++) {
    const date = new Date(cursor.getFullYear(), cursor.getMonth(), d);
    const isPast = date < today;
    const isClosed = CLOSED_DAYS.has(date.getDay());
    const isDisabled = isPast || isClosed;
    const isToday = sameDay(date, today);
    const isSelected = state.date && sameDay(date, state.date);

    const cell = document.createElement('div');
    cell.className = 'calendar__day';
    cell.textContent = d;
    cell.setAttribute('role', 'button');
    cell.setAttribute('tabindex', isDisabled ? '-1' : '0');
    cell.setAttribute('aria-label', `${d} ${MONTHS[cursor.getMonth()]}`);
    cell.setAttribute('aria-disabled', String(isDisabled));
    cell.setAttribute('aria-pressed', String(!!isSelected));

    if (isDisabled) cell.classList.add('calendar__day--disabled');
    if (isToday) cell.classList.add('calendar__day--today');
    if (isSelected) cell.classList.add('calendar__day--selected');

    if (!isDisabled) {
      cell.addEventListener('click', () => onDayClick(date));
      cell.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onDayClick(date); }
      });
    }

    grid.appendChild(cell);
  }
}

function onDayClick(date) {
  state.date = date;
  state.time = null;
  renderCalendar();
  renderSlots();
  if (onChangeCallback) onChangeCallback();
}

function renderSlots() {
  const grid = $('#slotGrid');
  const sub = $('#slotsSub');
  grid.innerHTML = '';

  if (!state.date) {
    sub.textContent = 'Выберите дату';
    return;
  }

  sub.textContent = fmtDateFull(state.date);

  // TODO: replace with real API call — GET /api/taken-slots?date=YYYY-MM-DD
  const seed = state.date.getDate();
  ALL_SLOTS.forEach((time, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'slot';
    btn.textContent = time;

    const isTaken = (i + seed) % 4 === 1; // demo only
    if (isTaken) {
      btn.disabled = true;
      btn.setAttribute('aria-label', `${time} — занято`);
    } else {
      btn.setAttribute('aria-label', `Время ${time}`);
    }

    if (state.time === time) {
      btn.classList.add('slot--active');
      btn.setAttribute('aria-pressed', 'true');
    }

    btn.addEventListener('click', () => {
      state.time = time;
      renderSlots();
      if (onChangeCallback) onChangeCallback();
    });

    grid.appendChild(btn);
  });
}
