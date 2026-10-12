/** Accessible tabs keep every view mounted, preserving edits and live polling. */
export function mountTabs(root, onChange = () => {}) {
  const owned = selector => [...root.querySelectorAll(selector)].filter(el => el.closest('[data-tabs]') === root);
  const buttons = owned('[data-tab-target]');
  const panels = owned('[data-tab-panel]');
  function activate(key, focus = false) {
    const target = buttons.find(button => button.dataset.tabTarget === key);
    if (!target) return;
    for (const button of buttons) {
      const selected = button === target;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
    for (const panel of panels) panel.hidden = panel.dataset.tabPanel !== key;
    if (focus) target.focus();
    onChange(key);
  }
  for (const [index, button] of buttons.entries()) {
    button.addEventListener('click', () => activate(button.dataset.tabTarget));
    button.addEventListener('keydown', event => {
      let next;
      if (['ArrowRight', 'ArrowDown'].includes(event.key)) next = (index + 1) % buttons.length;
      if (['ArrowLeft', 'ArrowUp'].includes(event.key)) next = (index - 1 + buttons.length) % buttons.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = buttons.length - 1;
      if (next !== undefined) {
        event.preventDefault();
        activate(buttons[next].dataset.tabTarget, true);
      }
    });
  }
  activate(buttons.find(button => button.getAttribute('aria-selected') === 'true')?.dataset.tabTarget || buttons[0]?.dataset.tabTarget);
  return { activate };
}
