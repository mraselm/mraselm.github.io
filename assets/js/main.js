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
      navToggle.classList.toggle('active');
      // Prevent body scroll when nav is open on mobile
      document.body.style.overflow = navLinks.classList.contains('open') ? 'hidden' : '';
    });

    navLinks.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navLinks.classList.remove('open');
        navToggle.classList.remove('active');
        document.body.style.overflow = '';
      });
    });

    // Close nav when clicking outside
    document.addEventListener('click', (e) => {
      if (navLinks.classList.contains('open') && 
          !navLinks.contains(e.target) && 
          !navToggle.contains(e.target)) {
        navLinks.classList.remove('open');
        navToggle.classList.remove('active');
        document.body.style.overflow = '';
      }
    });

    // Close nav on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && navLinks.classList.contains('open')) {
        navLinks.classList.remove('open');
        navToggle.classList.remove('active');
        document.body.style.overflow = '';
        navToggle.focus();
      }
    });
  }

  // Hide header on scroll down, show on scroll up (mobile only)
  let lastScroll = 0;
  const header = document.querySelector('.site-header');
  
  if (header && window.innerWidth <= 768) {
    window.addEventListener('scroll', () => {
      const currentScroll = window.scrollY;
      
      if (currentScroll <= 50) {
        header.style.transform = 'translateY(0)';
        return;
      }
      
      if (currentScroll > lastScroll && currentScroll > 150) {
        // Scrolling down - hide header
        header.style.transform = 'translateY(-100%)';
      } else {
        // Scrolling up - show header
        header.style.transform = 'translateY(0)';
      }
      
      lastScroll = currentScroll;
    }, { passive: true });
  }

  // Add header transition for smooth hide/show
  if (header) {
    header.style.transition = 'transform 0.3s ease';
  }

  // Set active nav link based on current path
  const currentPath = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(link => {
    const href = link.getAttribute('href');
    if (href === currentPath || (href !== '/' && currentPath.startsWith(href.replace(/\/$/, '')))) {
      link.classList.add('active');
    }
  });

  // Update active nav on scroll for hash links
  const sections = document.querySelectorAll('section[id]');
  const navItems = document.querySelectorAll('.nav-links a[href^="#"]');
  
  const observerOptions = { rootMargin: '-20% 0px -70% 0px' };
  const sectionObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        navItems.forEach(item => {
          item.classList.toggle('active', item.getAttribute('href') === `#${entry.target.id}`);
        });
      }
    });
  }, observerOptions);

  sections.forEach(section => sectionObserver.observe(section));

  // Scroll-triggered reveal animations
  const revealElements = document.querySelectorAll('.project-card, .skill-card, .section-header, .contact-card, .contact-form');
  const revealObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -50px 0px' });

  revealElements.forEach(el => {
    el.classList.add('reveal-on-scroll');
    revealObserver.observe(el);
  });

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

  // ═══════════════════════════════════════════════════════════
  // MICRO-CONVERSION TRACKING
  // ═══════════════════════════════════════════════════════════

  // Track project card clicks
  document.querySelectorAll('.project-card .btn')?.forEach(btn => {
    btn.addEventListener('click', () => {
      const projectTitle = btn.closest('.project-card')?.querySelector('h3')?.textContent || 'Unknown';
      const action = btn.textContent.trim();
      if (typeof window.gtag === 'function') {
        window.gtag('event', 'project_click', {
          event_category: 'Engagement',
          event_label: `${projectTitle} - ${action}`
        });
      }
    });
  });

  // Track scroll depth milestones (25%, 50%, 75%, 100%)
  const scrollDepths = { 25: false, 50: false, 75: false, 100: false };
  const trackScrollDepth = () => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const scrollPercent = Math.round((scrollTop / docHeight) * 100);
    
    Object.keys(scrollDepths).forEach(depth => {
      if (scrollPercent >= parseInt(depth) && !scrollDepths[depth]) {
        scrollDepths[depth] = true;
        if (typeof window.gtag === 'function') {
          window.gtag('event', 'scroll_depth', {
            event_category: 'Engagement',
            event_label: `${depth}%`,
            value: parseInt(depth)
          });
        }
      }
    });
  };
  window.addEventListener('scroll', trackScrollDepth, { passive: true });

  // Track time on page (30s, 60s, 120s, 300s)
  const timeThresholds = [30, 60, 120, 300];
  let timeTracked = {};
  const startTime = Date.now();
  
  const trackTimeOnPage = () => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    timeThresholds.forEach(threshold => {
      if (elapsed >= threshold && !timeTracked[threshold]) {
        timeTracked[threshold] = true;
        if (typeof window.gtag === 'function') {
          window.gtag('event', 'time_on_page', {
            event_category: 'Engagement',
            event_label: `${threshold}s`,
            value: threshold
          });
        }
      }
    });
  };
  setInterval(trackTimeOnPage, 5000);

  // Track PDF/CV views
  document.querySelectorAll('a[href*="drive.google.com"]')?.forEach(link => {
    link.addEventListener('click', () => {
      const isDownload = link.href.includes('export=download');
      const eventName = isDownload ? 'cv_download' : 'cv_view';
      if (typeof window.gtag === 'function') {
        window.gtag('event', eventName, {
          event_category: 'Conversion',
          event_label: link.textContent.trim()
        });
      }
    });
  });

  // Track external link clicks
  document.querySelectorAll('a[target="_blank"]')?.forEach(link => {
    link.addEventListener('click', () => {
      const url = new URL(link.href);
      if (typeof window.gtag === 'function') {
        window.gtag('event', 'external_link', {
          event_category: 'Outbound',
          event_label: url.hostname
        });
      }
    });
  });

  // Track section views
  const sectionNames = ['projects', 'for-you', 'skills', 'contact'];
  const sectionViewObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const sectionId = entry.target.id;
        if (typeof window.gtag === 'function') {
          window.gtag('event', 'section_view', {
            event_category: 'Engagement',
            event_label: sectionId
          });
        }
        sectionViewObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });

  sectionNames.forEach(id => {
    const section = document.getElementById(id);
    if (section) sectionViewObserver.observe(section);
  });

  // ═══════════════════════════════════════════════════════════

  // Scroll progress indicator
  const scrollProgress = document.querySelector('.scroll-progress');
  if (scrollProgress) {
    const updateScrollProgress = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const scrollPercent = docHeight > 0 ? (scrollTop / docHeight) * 100 : 0;
      scrollProgress.style.width = `${scrollPercent}%`;
    };
    window.addEventListener('scroll', updateScrollProgress, { passive: true });
    updateScrollProgress();
  }

  // Back to top button
  const backToTop = document.querySelector('.back-to-top');
  if (backToTop) {
    window.addEventListener('scroll', () => {
      backToTop.classList.toggle('visible', window.scrollY > 400);
    }, { passive: true });

    backToTop.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // Visitor Counter (using CountAPI)
  const visitorCountEl = document.getElementById('visitor-count');
  if (visitorCountEl) {
    // Check if this session already counted
    const counted = sessionStorage.getItem('visitor-counted');
    const endpoint = counted 
      ? 'https://api.countapi.xyz/get/raselmia-portfolio/visitors'
      : 'https://api.countapi.xyz/hit/raselmia-portfolio/visitors';
    
    fetch(endpoint)
      .then(res => res.json())
      .then(data => {
        if (data.value) {
          visitorCountEl.textContent = data.value.toLocaleString();
          sessionStorage.setItem('visitor-counted', 'true');
        }
      })
      .catch(() => {
        visitorCountEl.textContent = '—';
      });
  }

  // Share dropdown toggle
  const shareDropdown = document.querySelector('.share-dropdown');
  if (shareDropdown) {
    const shareBtn = shareDropdown.querySelector('.share-btn');
    const shareMenu = shareDropdown.querySelector('.share-menu');
    const copyLinkBtn = shareDropdown.querySelector('.copy-link-btn');

    // Toggle dropdown on button click
    shareBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      shareDropdown.classList.toggle('open');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
      if (!shareDropdown.contains(e.target)) {
        shareDropdown.classList.remove('open');
      }
    });

    // Copy link functionality
    if (copyLinkBtn) {
      copyLinkBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const url = window.location.href;
        navigator.clipboard.writeText(url).then(() => {
          const originalText = copyLinkBtn.innerHTML;
          copyLinkBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
          setTimeout(() => {
            copyLinkBtn.innerHTML = originalText;
          }, 2000);
        }).catch(() => {
          // Fallback for older browsers
          const textarea = document.createElement('textarea');
          textarea.value = url;
          document.body.appendChild(textarea);
          textarea.select();
          document.execCommand('copy');
          document.body.removeChild(textarea);
          const originalText = copyLinkBtn.innerHTML;
          copyLinkBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
          setTimeout(() => {
            copyLinkBtn.innerHTML = originalText;
          }, 2000);
        });
        shareDropdown.classList.remove('open');
      });
    }
  }
});
