// front/js/chat.js
const API = (path) => `/api${path}`;
let SID = null;

async function init() {
  const r = await fetch(API('/session'), {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({})
  });
  const j = await r.json();
  SID = j.sid;
  bindSettings();
}

function bindSettings() {
  const pro = document.getElementById('proactiveToggle');
  const freq = document.getElementById('freq');
  async function push() {
    await fetch(API('/settings'),{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({sid: SID, proactive: pro.checked, frequency: freq.value})
    });
  }
  pro.onchange = push; freq.onchange = push;
}

function appendBubble(role, html) {
  const wrap = document.getElementById('chat');
  const div = document.createElement('div');
  div.className = role;
  div.innerHTML = html;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
}

function renderSuggestion(card) {
  if(!card) return "";
  const alt = (card.alt||[]).map(x => `<a href="${x.url}" target="_blank" rel="noopener">${x.title}</a>`).join(" · ");
  return `
    <div class="suggestion-card">
      <div class="title">${card.title}</div>
      <div class="meta">${card.reason}</div>
      ${card.url ? `<div><a href="${card.url}" target="_blank" rel="noopener">Open</a>${alt?` · ${alt}`:''}</div>` : ""}
    </div>
  `;
}

document.getElementById('chatForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const input = document.getElementById('msg');
  const text = input.value.trim();
  if(!text) return;
  appendBubble('user', text);
  input.value = "";

  const res = await fetch(API('/chat'), {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({sid: SID, text})
  });
  const j = await res.json();
  const cardHTML = j?.proactive?.card ? renderSuggestion(j.proactive.card) : "";
  appendBubble('assistant', `${escapeHTML(j.reply)}${cardHTML}`);
});

function escapeHTML(s){
  return s.replace(/[&<>'"]/g, (c)=>({
    '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'
  }[c]));
}

init();
