document.addEventListener('DOMContentLoaded', () => {
  const navToggle = document.querySelector('.nav-toggle');
  const navLinks = document.querySelector('.nav-links');
  const contactForms = document.querySelectorAll('form.contact-form');
  const toast = document.querySelector('.form-toast');
  const themeToggle = document.querySelector('.theme-toggle');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
  const body = document.body;

  const GISCUS_THEME_LIGHT = 'light';
  const GISCUS_THEME_DARK = 'dark';
  let giscusObserver;

  const updateGiscusTheme = (isDark) => {
    const theme = isDark ? GISCUS_THEME_DARK : GISCUS_THEME_LIGHT;
    const giscusScript = document.querySelector('script[src="https://giscus.app/client.js"]');
    const existingFrame = document.querySelector('iframe.giscus-frame');
    if (!giscusScript && !existingFrame) {
      return;
    }

    if (giscusScript) {
      giscusScript.setAttribute('data-theme', theme);
    }

    const applyTheme = () => {
      const iframe = document.querySelector('iframe.giscus-frame');
      if (!iframe || !iframe.contentWindow) {
        return false;
      }
      iframe.contentWindow.postMessage(
        { giscus: { setConfig: { theme } } },
        'https://giscus.app'
      );
      return true;
    };

    if (applyTheme()) {
      if (giscusObserver) {
        giscusObserver.disconnect();
        giscusObserver = null;
      }
      return;
    }

    if (!giscusObserver) {
      giscusObserver = new MutationObserver(() => {
        if (applyTheme()) {
          giscusObserver.disconnect();
          giscusObserver = null;
        }
      });
      giscusObserver.observe(document.body, { childList: true, subtree: true });
    }
  };

  const setTheme = (mode, persist = true) => {
    const isDark = mode === 'dark';
    body.classList.toggle('theme-dark', isDark);
    if (themeToggle) {
      themeToggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
    }
    if (persist) localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateGiscusTheme(isDark);
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

  // Unified discovery search (projects + data stories)
  const discoveryRoots = document.querySelectorAll('[data-discovery-root]');
  if (discoveryRoots.length) {
    const indexGroups = new Map();
    discoveryRoots.forEach(root => {
      const indexUrl = root.getAttribute('data-discovery-index') || '/assets/data/discovery-index.json';
      if (!indexGroups.has(indexUrl)) {
        indexGroups.set(indexUrl, []);
      }
      indexGroups.get(indexUrl).push(root);
    });

    const normalize = (value) => value.toLowerCase().trim();
    const typeLabels = { project: 'Project', story: 'Data Story' };

    const buildTagList = (items) => {
      const tagMap = new Map();
      items.forEach(item => {
        (item.tags || []).forEach(tag => {
          const key = normalize(tag);
          if (!tagMap.has(key)) {
            tagMap.set(key, tag);
          }
        });
      });
      return Array.from(tagMap.entries())
        .map(([key, label]) => ({ key, label }))
        .sort((a, b) => a.label.localeCompare(b.label));
    };

    const renderDiscovery = (root, items, tags) => {
      const input = root.querySelector('[data-discovery-query]');
      const tagContainer = root.querySelector('[data-discovery-tags]');
      const results = root.querySelector('[data-discovery-results]');
      const empty = root.querySelector('[data-discovery-empty]');

      if (!input || !tagContainer || !results) return;

      const state = { query: '', tags: new Set() };
      const emptyDefault = empty?.dataset.emptyDefault || 'Start typing or pick a tag to see results.';
      const emptyNoResults = empty?.dataset.emptyNoResults || 'No matches found.';

      const allButton = document.createElement('button');
      allButton.type = 'button';
      allButton.className = 'discovery-tag-btn active';
      allButton.dataset.tag = 'all';
      allButton.setAttribute('aria-pressed', 'true');
      allButton.textContent = 'All';
      tagContainer.appendChild(allButton);

      tags.forEach(tag => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'discovery-tag-btn';
        button.dataset.tag = tag.key;
        button.setAttribute('aria-pressed', 'false');
        button.textContent = tag.label;
        tagContainer.appendChild(button);
      });

      const updateTagButtons = () => {
        const buttons = tagContainer.querySelectorAll('.discovery-tag-btn');
        buttons.forEach(button => {
          const tag = button.dataset.tag;
          const isActive = tag === 'all' ? state.tags.size === 0 : state.tags.has(tag);
          button.classList.toggle('active', isActive);
          button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
      };

      const renderResults = () => {
        const query = normalize(state.query);
        const activeTags = Array.from(state.tags);
        const hasFilter = query.length > 0 || activeTags.length > 0;

        results.innerHTML = '';

        if (!hasFilter) {
          if (empty) {
            empty.textContent = emptyDefault;
            empty.hidden = false;
          }
          return;
        }

        const filtered = items.filter(item => {
          const text = [
            item.title,
            item.description,
            (item.tags || []).join(' '),
            item.type
          ].join(' ').toLowerCase();

          const matchesQuery = !query || text.includes(query);
          const matchesTags = activeTags.length === 0
            || (item.tags || []).some(tag => activeTags.includes(normalize(tag)));
          return matchesQuery && matchesTags;
        });

        if (!filtered.length) {
          if (empty) {
            empty.textContent = emptyNoResults;
            empty.hidden = false;
          }
          return;
        }

        if (empty) empty.hidden = true;

        filtered.forEach(item => {
          const card = document.createElement('article');
          card.className = 'discovery-card';

          const meta = document.createElement('div');
          meta.className = 'discovery-meta';
          const type = document.createElement('span');
          type.className = 'discovery-type';
          type.textContent = typeLabels[item.type] || 'Item';
          meta.appendChild(type);

          const title = document.createElement('h3');
          const titleLink = document.createElement('a');
          titleLink.href = item.url;
          titleLink.textContent = item.title;
          title.appendChild(titleLink);

          const desc = document.createElement('p');
          desc.textContent = item.description || '';

          const tagList = document.createElement('div');
          tagList.className = 'discovery-tags';
          (item.tags || []).slice(0, 4).forEach(tag => {
            const chip = document.createElement('span');
            chip.className = 'discovery-tag';
            chip.textContent = tag;
            tagList.appendChild(chip);
          });

          const actions = document.createElement('div');
          actions.className = 'discovery-actions';
          const primary = document.createElement('a');
          primary.className = 'btn ghost';
          primary.href = item.url;
          primary.textContent = item.type === 'project' ? 'View project' : 'Read story';
          actions.appendChild(primary);

          if (item.type === 'project' && item.storyUrl) {
            const secondary = document.createElement('a');
            secondary.className = 'btn primary';
            secondary.href = item.storyUrl;
            secondary.textContent = 'Read case study';
            actions.appendChild(secondary);
          }

          if (item.type === 'story' && item.projectUrl) {
            const secondary = document.createElement('a');
            secondary.className = 'btn ghost';
            secondary.href = item.projectUrl;
            secondary.textContent = 'View in portfolio';
            actions.appendChild(secondary);
          }

          card.append(meta, title, desc, tagList, actions);
          results.appendChild(card);
        });
      };

      tagContainer.addEventListener('click', (event) => {
        const button = event.target.closest('.discovery-tag-btn');
        if (!button) return;
        const tag = button.dataset.tag;
        if (tag === 'all') {
          state.tags.clear();
        } else {
          if (state.tags.has(tag)) {
            state.tags.delete(tag);
          } else {
            state.tags.add(tag);
          }
        }
        updateTagButtons();
        renderResults();
      });

      input.addEventListener('input', (event) => {
        state.query = event.target.value || '';
        renderResults();
      });

      updateTagButtons();
      renderResults();
    };

    indexGroups.forEach((roots, indexUrl) => {
      fetch(indexUrl)
        .then(response => response.json())
        .then(items => {
          if (!Array.isArray(items)) return;
          const tagList = buildTagList(items);
          roots.forEach(root => renderDiscovery(root, items, tagList));
        })
        .catch(() => {
          roots.forEach(root => {
            const empty = root.querySelector('[data-discovery-empty]');
            if (empty) {
              empty.textContent = 'Discovery data is unavailable right now.';
              empty.hidden = false;
            }
          });
        });
    });
  }
});
