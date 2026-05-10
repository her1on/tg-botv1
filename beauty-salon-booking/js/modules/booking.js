import { supabase } from '../config/supabase.js';
import { $, $$, setBtn, escapeHtml } from '../utils/domHelpers.js';
import { validateName, validatePhone } from '../utils/validation.js';
import { fmtPrice, fmtDateLong, fmtDateShort, fmtDateISO } from '../utils/formatters.js';
import { notify } from './notifications.js';
import { getSelectedService, resetService } from './services.js';
import { getSelectedDate, getSelectedTime, resetCalendar } from './calendar.js';

/**
 * Initialize the multi-step booking form: wire up all step navigation and submission.
 * @param {(step: number) => void} onStepChange - called whenever the active step changes
 */
export function initBooking(onStepChange) {
  $('#next1').addEventListener('click', () => {
    if (getSelectedService()) advance(2, onStepChange);
  });

  $('#next2').addEventListener('click', () => {
    if (getSelectedDate() && getSelectedTime()) advance(3, onStepChange);
  });

  $$('.step-btn--back').forEach((btn) => {
    btn.addEventListener('click', () => {
      const from = parseInt(btn.dataset.back, 10);
      advance(from - 1, onStepChange);
    });
  });

  $('#submitBooking').addEventListener('click', () => handleSubmit(onStepChange));
  $('#restartBtn').addEventListener('click', () => restart(onStepChange));

  // Live validation: clear error state as user fixes input
  $('#name').addEventListener('input', (e) => {
    if (e.target.value.trim()) e.target.closest('.field').classList.remove('field--error');
  });
  $('#phone').addEventListener('input', (e) => {
    if (validatePhone(e.target.value.trim())) e.target.closest('.field').classList.remove('field--error');
  });
}

/**
 * Enable or disable the "Continue" button on step 1.
 * @param {boolean} enabled
 */
export function setStep1Continue(enabled) {
  $('#next1').disabled = !enabled;
}

/**
 * Enable or disable the "Continue" button on step 2.
 * @param {boolean} enabled
 */
export function setStep2Continue(enabled) {
  $('#next2').disabled = !enabled;
}

// ---------- private ----------

function advance(step, onStepChange) {
  $$('.step-panel').forEach((p) => {
    p.classList.toggle('step-panel--active', parseInt(p.dataset.panel, 10) === step);
  });

  $$('.step-pill').forEach((pill) => {
    const s = parseInt(pill.dataset.step, 10);
    pill.classList.toggle('step-pill--active', s === step);
    pill.classList.toggle('step-pill--complete', s < step);
  });

  if (step === 3) renderReview();
  if (onStepChange) onStepChange(step);
}

function renderReview() {
  const svc = getSelectedService();
  const date = getSelectedDate();
  const time = getSelectedTime();
  if (!svc || !date || !time) return;

  $('#reviewSummary').innerHTML = `
    <div class="review-summary__item">
      <span class="review-summary__label">Услуга</span>
      <span class="review-summary__value">${escapeHtml(svc.name)}</span>
    </div>
    <div class="review-summary__item">
      <span class="review-summary__label">Дата</span>
      <span class="review-summary__value">${escapeHtml(fmtDateShort(date))}</span>
    </div>
    <div class="review-summary__item">
      <span class="review-summary__label">Время</span>
      <span class="review-summary__value">${escapeHtml(time)}</span>
    </div>
    <div class="review-summary__item">
      <span class="review-summary__label">Итого</span>
      <span class="review-summary__value">${fmtPrice(svc.price)}</span>
    </div>
  `;
}

async function handleSubmit(onStepChange) {
  const nameEl = $('#name');
  const phoneEl = $('#phone');
  const name = nameEl.value.trim();
  const phone = phoneEl.value.trim();
  const notes = $('#notes').value.trim();

  const nameOk = validateName(name);
  const phoneOk = validatePhone(phone);

  nameEl.closest('.field').classList.toggle('field--error', !nameOk);
  phoneEl.closest('.field').classList.toggle('field--error', !phoneOk);

  if (!nameOk || !phoneOk) {
    notify.error('Пожалуйста, исправьте выделенные поля.');
    return;
  }

  // Guard: these should always be set at step 3, but defend against edge cases
  const svc = getSelectedService();
  const date = getSelectedDate();
  const time = getSelectedTime();

  if (!svc || !date || !time) {
    notify.error('Произошла ошибка. Пожалуйста, начните запись заново.');
    return;
  }

  const submitBtn = $('#submitBooking');
  setBtn(submitBtn, true, '<span aria-hidden="true">⏳</span> Отправка…');

  const payload = {
    name,
    phone,
    service: svc.name,
    appointment_date: fmtDateISO(date),
    appointment_time: time,
    ...(notes && { notes }),
  };

  try {
    if (supabase) {
      const { error } = await supabase.from('appointments').insert(payload);
      if (error) throw error;
    } else {
      // Demo mode: simulate network delay
      await new Promise((r) => setTimeout(r, 700));
      console.info('[demo] appointment payload:', payload);
    }

    renderFinalSummary(svc, date, time, name, phone);
    advance(4, onStepChange);
    notify.success('Запись подтверждена! Ждём вас.');
  } catch (err) {
    console.error('[booking] submit error:', err);
    notify.error('Не удалось отправить запись. Попробуйте ещё раз или позвоните нам.');
  } finally {
    setBtn(submitBtn, false, 'Подтвердить запись <span aria-hidden="true">→</span>');
  }
}

function renderFinalSummary(svc, date, time, name, phone) {
  $('#finalSummary').innerHTML = `
    <div class="summary__row">
      <span class="summary__label">Гость</span>
      <span class="summary__value">${escapeHtml(name)}</span>
    </div>
    <div class="summary__row">
      <span class="summary__label">Телефон</span>
      <span class="summary__value">${escapeHtml(phone)}</span>
    </div>
    <div class="summary__row">
      <span class="summary__label">Услуга</span>
      <span class="summary__value">${escapeHtml(svc.name)}</span>
    </div>
    <div class="summary__row">
      <span class="summary__label">Когда</span>
      <span class="summary__value">${escapeHtml(fmtDateLong(date))} · ${escapeHtml(time)}</span>
    </div>
    <div class="summary__row summary__row--total">
      <span class="summary__label">Итого</span>
      <span class="summary__value">${fmtPrice(svc.price)}</span>
    </div>
  `;
}

function restart(onStepChange) {
  $('#name').value = '';
  $('#phone').value = '';
  $('#notes').value = '';
  $$('.field').forEach((f) => f.classList.remove('field--error'));

  resetService();
  resetCalendar();

  setBtn($('#next1'), true);
  setBtn($('#next2'), true);

  advance(1, onStepChange);
  document.getElementById('booking').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
