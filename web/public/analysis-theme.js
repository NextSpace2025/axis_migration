(() => {
  const control=document.getElementById('viewer-theme');
  const key = 'axis-viewer-theme';
  function apply(value) {
    const theme = value === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    if(control) control.value = theme;
    document.dispatchEvent(new Event('axis:theme-change'));
  }
  let savedTheme;
  try { savedTheme = localStorage.getItem(key); } catch {}
  apply(savedTheme);
  control?.addEventListener('change', () => {
    apply(control.value);
    try { localStorage.setItem(key, control.value); } catch {}
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(event.newValue);
  });
})();
