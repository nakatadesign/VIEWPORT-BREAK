import { PRESETS, API_FLOOR, setWidth, getTargetWindow } from './core.js';

const $ = (id) => document.getElementById(id);

function paintWidth(w, h) {
  $('curW').textContent = w ?? '—';
  $('curH').textContent = h ? `× ${h}` : '';
  for (const b of $('grid').children) {
    b.classList.toggle('is-current', Number(b.dataset.w) === w);
  }
}

function say(text, kind) {
  const el = $('msg');
  el.textContent = text || '';
  el.className = 'msg' + (kind ? ` is-${kind}` : '');
}

function buildGrid() {
  const frag = document.createDocumentFragment();
  for (const p of PRESETS) {
    const b = document.createElement('button');
    b.className = 'btn';
    b.textContent = p.label;
    b.dataset.w = p.w;
    b.title = `${p.w}px — ${p.note}`;
    b.addEventListener('click', () => apply(p.w));
    frag.appendChild(b);
  }
  $('grid').appendChild(frag);
}

async function apply(w) {
  say('適用中…');
  try {
    const r = await setWidth(w);
    paintWidth(r.width, r.height);
    // native host の状態は常設表示しない。到達できなかった瞬間だけ理由を出す。
    if (r.clamped && r.path === 'api') {
      say(
        `${r.requested}px に届かず ${r.width}px で止まった。` +
        `${API_FLOOR}px 未満には native host が要る（${r.hostUnavailable
          ? '未登録: Chrome を一度起動してから Applications の VIEWPORT BREAK をもう一度開く'
          : r.hostError}）。`,
        'err'
      );
    } else if (r.clamped) {
      say(`${r.requested}px を要求したが ${r.width}px になった。`, 'warn');
    } else {
      say(`${r.width}px`);
    }
  } catch (e) {
    say(`失敗: ${e.message}`, 'err');
  }
}

async function init() {
  buildGrid();

  const win = await getTargetWindow();
  paintWidth(win.width, win.height);

  $('customForm').addEventListener('submit', (e) => {
    e.preventDefault();
    const v = parseInt($('customW').value, 10);
    if (Number.isFinite(v) && v >= 1 && v <= 4000) apply(v);
    else say('1〜4000 の整数を入れる。', 'err');
  });
}

init();
