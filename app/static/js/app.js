/* OneHubAI shared front-end helpers */

(function themeBoot() {
  const saved = localStorage.getItem('onehub-theme') || document.documentElement.getAttribute('data-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
})();

function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('onehub-theme', next);
  const ic = document.getElementById('themeIcon');
  if (ic) ic.textContent = next === 'dark' ? '🌙' : '☀️';
  // Persist theme to DB if logged in
  postJson('/app/settings/theme', { theme: next }).catch(() => {});
}

function spawnParticles(count) {
  const root = document.querySelector('.particles');
  if (!root) return;
  const colors = ['#7c5cff', '#00e0ff', '#ff5cf2', '#34f5c5'];
  for (let i = 0; i < count; i++) {
    const s = document.createElement('span');
    const size = 3 + Math.random() * 6;
    s.style.width = s.style.height = `${size}px`;
    s.style.left = `${Math.random() * 100}vw`;
    s.style.background = colors[Math.floor(Math.random() * colors.length)];
    s.style.boxShadow = `0 0 12px ${s.style.background}`;
    s.style.animationDuration = `${10 + Math.random() * 20}s`;
    s.style.animationDelay = `${-Math.random() * 20}s`;
    root.appendChild(s);
  }
}

async function postJson(url, body) {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrf || '',
    },
    body: JSON.stringify(body || {}),
  });
  return res.json();
}

async function postForm(url, formData) {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrf || '' },
    body: formData,
  });
  return res.json();
}

function escapeHtml(str) {
  return (str || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

function markdownLite(text) {
  if (!text) return '';

  // ── Handle Markdown tables BEFORE escaping ──
  const tableRegex = /(\|.+\|\n\|[-| :]+\|\n(?:\|.+\|\n?)+)/g;
  const tables = [];
  text = text.replace(tableRegex, (match) => {
    const rows = match.trim().split('\n');
    let tableHtml = '<div style="overflow-x:auto;margin:1rem 0;"><table class="md-table"><thead>';
    let inBody = false;
    rows.forEach((row, idx) => {
      if (idx === 1 && row.match(/^[\|: -]+$/)) {
        tableHtml += '</thead><tbody>';
        inBody = true;
        return;
      }
      const cells = row.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      const tag = (!inBody) ? 'th' : 'td';
      tableHtml += '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
    });
    tableHtml += '</tbody></table></div>';
    const placeholder = `__TABLE_${tables.length}__`;
    tables.push(tableHtml);
    return placeholder;
  });

  let html = escapeHtml(text);

  // Restore tables
  tables.forEach((t, i) => {
    html = html.replace(`__TABLE_${i}__`, t);
  });

  html = html.replace(/^### (.*)$/gm, '<h5 style="margin:.8rem 0 .4rem;">$1</h5>');
  html = html.replace(/^## (.*)$/gm, '<h4 style="margin:.8rem 0 .4rem;">$1</h4>');
  html = html.replace(/^# (.*)$/gm, '<h3 style="margin:.8rem 0 .4rem;">$1</h3>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(212,175,55,0.12);padding:1px 5px;border-radius:4px;">$1</code>');
  // Numbered lists
  html = html.replace(/^\d+\.\s+(.+)/gm, '<li>$1</li>');
  // Bullet lists
  html = html.replace(/^[-*•]\s+(.+)/gm, '<li>$1</li>');
  // Wrap consecutive <li> in <ul>
  html = html.replace(/(<li>.*<\/li>\n?)+/g, m => `<ul style="padding-left:1.4rem;margin:.5rem 0;">${m}</ul>`);
  html = html.replace(/\n\n/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');
  // Remove stray pipe characters that are not inside table markup
  html = html.replace(/(?<!<[^>]*)\|(?![^<]*>)/g, '');
  return `<p style="margin:0;">${html}</p>`;
}

document.addEventListener('DOMContentLoaded', () => {
  spawnParticles(18);
  const ic = document.getElementById('themeIcon');
  if (ic) {
    const t = document.documentElement.getAttribute('data-theme');
    ic.textContent = t === 'dark' ? '🌙' : '☀️';
  }
});

// ── Toast Notifications ──
(function() {
  let container = null;
  function getContainer() {
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }
  window.showToast = function(msg, type = 'info') {
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    const t = document.createElement('div');
    t.className = `toast-msg ${type}`;
    t.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${msg}`;
    getContainer().appendChild(t);
    setTimeout(() => {
      t.style.animation = 'toast-out 0.3s ease forwards';
      setTimeout(() => t.remove(), 300);
    }, 3000);
  };
})();
