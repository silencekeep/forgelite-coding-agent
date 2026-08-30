(function () {
  const levels = new Set(["low", "medium", "high"]);

  function select(control, level) {
    if (!levels.has(level)) return false;
    control.dataset.level = level;
    control.querySelector("[data-thinking-label]").textContent = level[0].toUpperCase() + level.slice(1);
    control.querySelectorAll("[data-thinking-option]").forEach((option) => {
      option.setAttribute("aria-current", String(option.dataset.thinkingOption === level));
    });
    control.dispatchEvent(new CustomEvent("thinking-change", { detail: { level } }));
    return true;
  }

  document.querySelectorAll("[data-thinking-control]").forEach((control) => {
    const trigger = control.querySelector("[data-thinking-trigger]");
    const menu = control.querySelector("[data-thinking-menu]");
    trigger.addEventListener("click", () => {
      const expanded = trigger.getAttribute("aria-expanded") === "true";
      trigger.setAttribute("aria-expanded", String(!expanded));
      menu.hidden = expanded;
    });
    control.querySelectorAll("[data-thinking-option]").forEach((option) => {
      option.addEventListener("click", () => {
        select(control, option.dataset.thinkingOption);
        trigger.setAttribute("aria-expanded", "false");
        menu.hidden = true;
      });
    });
  });

  document.addEventListener("click", (event) => {
    document.querySelectorAll("[data-thinking-control]").forEach((control) => {
      if (control.contains(event.target)) return;
      control.querySelector("[data-thinking-menu]").hidden = true;
      control.querySelector("[data-thinking-trigger]").setAttribute("aria-expanded", "false");
    });
  });
  window.ThinkingIndicator = { select };
})();
