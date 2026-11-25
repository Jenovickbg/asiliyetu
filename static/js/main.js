document.documentElement.classList.add('js');
const toggle = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#navigation');
if (toggle && navigation) {
  toggle.hidden = false;
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    navigation.classList.toggle('open', open);
  });
  navigation.addEventListener('click', event => {
    if (event.target.closest('a')) {
      navigation.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });
}
document.querySelectorAll('form[data-submit]').forEach(form => {
  form.addEventListener('submit', () => {
    const button = form.querySelector('button[type="submit"], button:not([type])');
    if (button) {
      button.dataset.originalText = button.textContent;
      button.disabled = true;
      button.textContent = 'Enregistrement en cours…';
      form.setAttribute('aria-busy', 'true');
    }
  });
});
window.addEventListener('pageshow', () => {
  document.querySelectorAll('[data-original-text]').forEach(button => {
    button.disabled = false;
    button.textContent = button.dataset.originalText;
    button.closest('form').removeAttribute('aria-busy');
  });
});
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
const phone = document.querySelector('#telephone');
if (phone) {
  phone.inputMode = 'tel';
  const validatePhone = () => {
    const compact = phone.value.replace(/[\s().-]/g, '');
    const valid = /^(?:(?:\+|00)?243|0)?[89]\d{8}$/.test(compact);
    phone.setCustomValidity(!phone.value || valid ? '' : 'Utilisez un numéro mobile congolais valide, par exemple +243 812 345 678.');
  };
  phone.addEventListener('input', validatePhone);
  validatePhone();
}
const email = document.querySelector('#email');
if (email) email.type = 'email';
const poster = document.querySelector('[data-poster]');
const dialog = document.querySelector('#poster-dialog');
if (poster && dialog) {
  poster.addEventListener('click', () => dialog.showModal());
  dialog.querySelector('button').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
}
