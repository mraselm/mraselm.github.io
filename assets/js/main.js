document.addEventListener('DOMContentLoaded', () => {
  const navToggle = document.querySelector('.nav-toggle');
  const navLinks = document.querySelector('.nav-links');
  const contactForms = document.querySelectorAll('form.contact-form');
  const toast = document.querySelector('.form-toast');

  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      navLinks.classList.toggle('open');
    });

    navLinks.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => navLinks.classList.remove('open'));
    });
  }

  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', event => {
      const targetId = link.getAttribute('href');
      const target = document.querySelector(targetId);
      if (target) {
        event.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  contactForms.forEach(form => {
    form.addEventListener('submit', event => {
      event.preventDefault();
      const formData = new FormData(form);
      const email = form.querySelector('input[type="email"]');

      if (email && !email.value.includes('@')) {
        alert('Please enter a valid email address.');
        return;
      }

      fetch(form.action, {
        method: form.method,
        body: formData,
        headers: { Accept: 'application/json' }
      })
        .then(response => {
          if (response.ok) {
            form.reset();
            if (toast) {
              toast.classList.add('show');
              setTimeout(() => toast.classList.remove('show'), 3500);
            }
          } else {
            alert('There was a problem submitting your form.');
          }
        })
        .catch(() => alert('There was a problem submitting your form.'));
    });
  });

  document.querySelectorAll('[data-toggle="full"]')?.forEach(button => {
    button.addEventListener('click', () => {
      const targetId = button.getAttribute('data-target');
      const short = document.querySelector(`#${targetId} .short-content`);
      const full = document.querySelector(`#${targetId} .full-content`);
      if (!short || !full) return;
      const isHidden = full.style.display === 'none' || full.style.display === '';
      full.style.display = isHidden ? 'block' : 'none';
      short.style.display = isHidden ? 'none' : 'block';
      button.textContent = isHidden ? 'Show Less' : 'Read More';
    });
  });
});
