import { $, $$ } from '../utils/domHelpers.js';
import { fmtPrice } from '../utils/formatters.js';

/** @typedef {{ id: number, name: string, cat: string, duration: number, price: number, desc: string }} Service */

/** @type {Service[]} */
export const SERVICES = [
  { id: 1, name: 'Фирменный уход за лицом',    cat: 'Лицо',            duration: 75,  price: 9800,  desc: 'Индивидуальный уход с глубоким очищением, мягким пилингом и лифтинг-массажем розовым кварцем.' },
  { id: 2, name: 'Окрашивание волос',           cat: 'Волосы',          duration: 120, price: 15400, desc: 'Окрашивание у ведущего колориста — глянцевание, балаяж или ровный тон.' },
  { id: 3, name: 'Маникюр «Золото»',            cat: 'Ногти',           duration: 60,  price: 5200,  desc: 'Аккуратный маникюр со стойким веганским покрытием и маслом для кутикулы.' },
  { id: 4, name: 'Ламинирование ресниц',        cat: 'Брови и ресницы', duration: 50,  price: 6300,  desc: 'Завивка, подъём и окрашивание ресниц — мягкий результат без туши на 6 недель.' },
  { id: 5, name: 'Ароматерапевтический массаж', cat: 'Тело',            duration: 90,  price: 12600, desc: 'Массаж всего тела с растительными маслами, подобранными под ваше настроение.' },
  { id: 6, name: 'Архитектура бровей',          cat: 'Брови и ресницы', duration: 30,  price: 3900,  desc: 'Точная форма нитью и пинцетом с окрашиванием — индивидуально под ваше лицо.' },
];

/** @type {number|null} */
let selectedId = null;

/** @type {((id: number) => void)|null} */
let onSelectCallback = null;

/**
 * Initialize the services section grid and the step-1 option list.
 * @param {(id: number) => void} onSelect - called when user selects a service
 */
export function initServices(onSelect) {
  onSelectCallback = onSelect;
  renderServicesGrid();
  renderServiceOptions();
}

/**
 * Programmatically select a service by ID, updating all UI.
 * @param {number} id
 */
export function selectService(id) {
  selectedId = id;
  updateOptionHighlights();
  updateCardHighlights();
  if (onSelectCallback) onSelectCallback(id);
}

/**
 * Return the currently selected service object, or null.
 * @returns {Service|null}
 */
export function getSelectedService() {
  return SERVICES.find((s) => s.id === selectedId) ?? null;
}

/**
 * Clear service selection (used on booking restart).
 */
export function resetService() {
  selectedId = null;
  updateOptionHighlights();
  updateCardHighlights();
}

// ---------- private ----------

function renderServicesGrid() {
  const grid = $('#servicesGrid');
  if (!grid) return;

  SERVICES.forEach((svc) => {
    const card = document.createElement('article');
    card.className = 'service-card';
    card.dataset.svc = svc.id;
    card.innerHTML = `
      <div class="service-card__thumb" aria-hidden="true">
        <span class="service-card__thumb-tag">// ${svc.cat.toLowerCase()} imagery</span>
      </div>
      <span class="service-card__category">${svc.cat}</span>
      <h3 class="service-card__title">${svc.name}</h3>
      <p class="service-card__desc">${svc.desc}</p>
      <div class="service-card__meta">
        <span class="service-card__duration">${svc.duration} мин</span>
        <span class="service-card__price">${fmtPrice(svc.price)}</span>
      </div>
      <button class="service-card__select" data-select="${svc.id}" aria-label="Выбрать: ${svc.name}">
        Выбрать <span aria-hidden="true">→</span>
      </button>
    `;
    grid.appendChild(card);
  });

  grid.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-select]');
    if (!btn) return;
    selectService(parseInt(btn.dataset.select, 10));
    document.getElementById('booking').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

function renderServiceOptions() {
  const container = $('#svcOptions');
  if (!container) return;

  SERVICES.forEach((svc) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'svc-option';
    btn.dataset.svc = svc.id;
    btn.setAttribute('aria-label', `${svc.name}, ${svc.duration} мин, ${fmtPrice(svc.price)}`);
    btn.innerHTML = `
      <div>
        <div class="svc-option__name">${svc.name}</div>
        <div class="svc-option__meta">${svc.cat} · ${svc.duration} мин</div>
      </div>
      <div class="svc-option__price">${fmtPrice(svc.price)}</div>
    `;
    btn.addEventListener('click', () => selectService(svc.id));
    container.appendChild(btn);
  });
}

function updateOptionHighlights() {
  $$('.svc-option').forEach((opt) => {
    opt.classList.toggle('svc-option--active', parseInt(opt.dataset.svc, 10) === selectedId);
  });
}

function updateCardHighlights() {
  $$('.service-card').forEach((card) => {
    const isSelected = parseInt(card.dataset.svc, 10) === selectedId;
    card.classList.toggle('service-card--selected', isSelected);
    const btn = card.querySelector('.service-card__select');
    if (btn) btn.innerHTML = isSelected ? 'Выбрано ✓' : 'Выбрать <span aria-hidden="true">→</span>';
  });
}
