document.addEventListener('DOMContentLoaded', () => {
  const navToggle = document.querySelector('.nav-toggle');
  const navLinks = document.querySelector('.nav-links');
  const contactForms = document.querySelectorAll('form.contact-form');
  const toast = document.querySelector('.form-toast');
  const themeToggle = document.querySelector('.theme-toggle');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
  const body = document.body;

  const setTheme = (mode, persist = true) => {
    const isDark = mode === 'dark';
    body.classList.toggle('theme-dark', isDark);
    if (themeToggle) {
      themeToggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
    }
    if (persist) localStorage.setItem('theme', isDark ? 'dark' : 'light');
  };

  const storedTheme = localStorage.getItem('theme');
  if (storedTheme === 'dark' || storedTheme === 'light') {
    setTheme(storedTheme, false);
  } else {
    setTheme(prefersDark.matches ? 'dark' : 'light', false);
  }

  prefersDark.addEventListener('change', event => {
    if (!localStorage.getItem('theme')) {
      setTheme(event.matches ? 'dark' : 'light', false);
    }
  });

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const next = body.classList.contains('theme-dark') ? 'light' : 'dark';
      setTheme(next);
    });
  }

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

  // Track GA events for CTAs if gtag is available
  document.querySelectorAll('[data-ga-event]')?.forEach(link => {
    link.addEventListener('click', () => {
      const eventName = link.getAttribute('data-ga-event');
      const label = link.getAttribute('data-ga-label') || link.textContent.trim();
      if (typeof window.gtag === 'function' && eventName) {
        window.gtag('event', eventName, {
          event_category: 'CTA',
          event_label: label
        });
      }
    });
  });
});
