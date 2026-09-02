import assert from 'node:assert/strict';

let commandListener;
let mode = 'clamped';
let badgeText = null;
let title = null;

globalThis.chrome = {
  runtime: {
    async sendNativeMessage() {
      if (mode === 'success') {
        return { ok: true, bounds: { width: 375, height: 800 } };
      }
      throw new Error('native host が見つからない');
    },
  },
  windows: {
    async getCurrent() {
      if (mode === 'error') throw new Error('対象ウィンドウを取得できない');
      return { id: 1, state: 'normal', left: 0, top: 0, width: 900, height: 800 };
    },
    async update() {},
    async get() {
      return { id: 1, state: 'normal', left: 0, top: 0, width: 500, height: 800 };
    },
  },
  commands: {
    onCommand: {
      addListener(fn) {
        commandListener = fn;
      },
    },
  },
  action: {
    async setBadgeText({ text }) {
      badgeText = text;
    },
    async setBadgeBackgroundColor() {},
    async setTitle({ title: nextTitle }) {
      title = nextTitle;
    },
  },
};

await import('../background.js');
assert.equal(typeof commandListener, 'function');

await commandListener('width-375');
assert.equal(badgeText, '!');
assert.match(title, /375px に届かず 500px/);

mode = 'success';
await commandListener('width-375');
assert.equal(badgeText, '');
assert.equal(title, 'VIEWPORT BREAK — ウィンドウ幅を切り替える');

mode = 'error';
await commandListener('width-375');
assert.equal(badgeText, '!');
assert.match(title, /対象ウィンドウを取得できない/);

console.log('background.test.mjs: PASS');
