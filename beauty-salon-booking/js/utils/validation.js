/**
 * Check that a name field is not empty.
 * @param {string} name
 * @returns {boolean}
 */
export const validateName = (name) => name.trim().length >= 2 && name.trim().length <= 20;

/**
 * Loose international phone validation: at least 7 digits, only allowed chars.
 * @param {string} phone
 * @returns {boolean}
 */
export const validatePhone = (phone) => {
  const digits = (phone || '').replace(/\D/g, '');
  return digits.length >= 7 && /^[\d\s+()\-]+$/.test(phone);
};
