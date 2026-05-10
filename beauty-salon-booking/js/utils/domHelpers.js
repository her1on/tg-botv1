/**
 * Shorthand for document.querySelector.
 * @param {string} selector
 * @param {Element|Document} [ctx=document]
 * @returns {Element|null}
 */
export const $ = (selector, ctx = document) => ctx.querySelector(selector);

/**
 * Shorthand for document.querySelectorAll, returns a real Array.
 * @param {string} selector
 * @param {Element|Document} [ctx=document]
 * @returns {Element[]}
 */
export const $$ = (selector, ctx = document) => [...ctx.querySelectorAll(selector)];

/**
 * Toggle a class on an element, optionally forcing the state.
 * @param {Element} el
 * @param {string} cls
 * @param {boolean} [force]
 */
export const toggleClass = (el, cls, force) => el.classList.toggle(cls, force);

/**
 * Set disabled state and inner HTML on a button simultaneously.
 * @param {HTMLButtonElement} btn
 * @param {boolean} disabled
 * @param {string} [html]
 */
export const setBtn = (btn, disabled, html) => {
  btn.disabled = disabled;
  if (html !== undefined) btn.innerHTML = html;
};

/**
 * Escape user-supplied strings before inserting into innerHTML.
 * Prevents XSS when building HTML from untrusted input.
 * @param {string} str
 * @returns {string}
 */
export const escapeHtml = (str) =>
  String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
