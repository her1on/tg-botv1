import { initServices } from './modules/services.js';
import { initCalendar, getSelectedDate, getSelectedTime } from './modules/calendar.js';
import { initBooking, setStep1Continue, setStep2Continue } from './modules/booking.js';

// ---- Nav scroll ----
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('nav--scrolled', window.scrollY > 30);
}, { passive: true });

// ---- Mobile menu ----
const menuToggle = document.getElementById('menuToggle');
const navLinks = document.getElementById('navLinks');
menuToggle.addEventListener('click', () => {
  const isOpen = navLinks.classList.toggle('nav__links--open');
  menuToggle.setAttribute('aria-expanded', String(isOpen));
});
document.querySelectorAll('#navLinks a').forEach((a) => {
  a.addEventListener('click', () => {
    navLinks.classList.remove('nav__links--open');
    menuToggle.setAttribute('aria-expanded', 'false');
  });
});

// ---- Services ----
initServices((serviceId) => {
  setStep1Continue(true);
});

// ---- Calendar ----
initCalendar(() => {
  setStep2Continue(!!(getSelectedDate() && getSelectedTime()));
});

// ---- Booking form ----
initBooking((step) => {
  // scroll booking panel into view on step change
  if (step > 1) {
    document.querySelector('.booking-panel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
});
