/**
 * Format a number as Russian Rubles.
 * @param {number} amount
 * @returns {string} e.g. "9 800 ₽"
 */
export const fmtPrice = (amount) => amount.toLocaleString('ru-RU') + ' ₽';

/**
 * Format a Date as a long Russian string (day of week, day, month, year).
 * @param {Date} date
 * @returns {string} e.g. "суббота, 10 мая 2026 г."
 */
export const fmtDateLong = (date) =>
  date.toLocaleDateString('ru-RU', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

/**
 * Format a Date as a short Russian string (day of week abbr, day, month abbr).
 * @param {Date} date
 * @returns {string} e.g. "сб, 10 мая"
 */
export const fmtDateShort = (date) =>
  date.toLocaleDateString('ru-RU', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });

/**
 * Format a Date as a long weekday + month + day string (no year).
 * @param {Date} date
 * @returns {string} e.g. "суббота, 10 мая"
 */
export const fmtDateFull = (date) =>
  date.toLocaleDateString('ru-RU', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

/**
 * Format a Date as ISO date string (YYYY-MM-DD).
 * @param {Date} date
 * @returns {string}
 */
export const fmtDateISO = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};
