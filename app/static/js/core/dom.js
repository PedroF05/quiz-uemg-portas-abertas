export function esc(value) {
  return String(value).replace(/[&<>"'`]/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;" }[char]
  ));
}

export function icon(name, className = "") {
  const classes = className ? `ico ${className}` : "ico";
  return `<img class="${classes}" src="/img/icons/${name}.png" alt="" aria-hidden="true" decoding="async">`;
}

export function $(selector, root = document) {
  return root.querySelector(selector);
}

export function $$(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}
