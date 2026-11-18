(() => {
  const selector = document.getElementById('dataset-select');
  const reviewing = document.body.hasAttribute('data-schema-review');
  if (!selector) return;

  selector.addEventListener('change', event => {
    if (!reviewing && !selector.value.startsWith('review:')) return;
    event.stopImmediatePropagation();
    const query = new URLSearchParams({dataset:selector.value, view:selector.value.startsWith('review:')?'combined':'graph'});
    location.assign('/?' + query);
  }, true);

  if (!reviewing) return;
  for (const [key, info] of Object.entries(window.APP_META?.datasets || {})) {
    selector.add(new Option(info.label, key));
  }
  const list = document.getElementById('nav-toggle');
  list.addEventListener('click', () => {
    list.setAttribute('aria-expanded', String(document.body.classList.toggle('nav-open')));
  });
  const theme = document.getElementById('viewer-theme');
  const applyTheme = mode => {
    document.documentElement.dataset.theme = mode === 'light' ? 'light' : 'dark';
    theme.value = document.documentElement.dataset.theme;
    document.dispatchEvent(new Event('axis:theme-change'));
  };
  try { applyTheme(localStorage.getItem('axis-viewer-theme')); } catch { applyTheme('dark'); }
  theme.addEventListener('change', () => {
    applyTheme(theme.value);
    try { localStorage.setItem('axis-viewer-theme', theme.value); } catch {}
  });
})();
