const TOAST_DURATION_MS = 4000;

/**
 * @param {string} message
 * @param {'success'|'error'|'info'} type
 */
function createToast(message, type) {
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.textContent = message;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'polite');
  document.body.appendChild(toast);

  requestAnimationFrame(() => toast.classList.add('toast--visible'));

  setTimeout(() => {
    toast.classList.remove('toast--visible');
    toast.addEventListener('transitionend', () => toast.remove(), { once: true });
  }, TOAST_DURATION_MS);
}

/** Toast notification helpers. */
export const notify = {
  /** @param {string} msg */
  success: (msg) => createToast(msg, 'success'),
  /** @param {string} msg */
  error: (msg) => createToast(msg, 'error'),
  /** @param {string} msg */
  info: (msg) => createToast(msg, 'info'),
};
