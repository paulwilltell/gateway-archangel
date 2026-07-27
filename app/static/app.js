(() => {
  const forms = document.querySelectorAll('[data-count-form]');
  for (const form of forms) {
    const textarea = form.querySelector('textarea[maxlength]');
    const counter = form.querySelector('.char-count');
    if (!textarea || !counter) continue;
    const update = () => {
      const max = Number(textarea.getAttribute('maxlength')) || 0;
      counter.textContent = `${textarea.value.length.toLocaleString()} / ${max.toLocaleString()}`;
      counter.dataset.nearLimit = String(max > 0 && textarea.value.length / max > 0.9);
    };
    textarea.addEventListener('input', update);
    update();
  }
})();
