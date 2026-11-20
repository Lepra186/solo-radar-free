import test from "node:test";
import assert from "node:assert/strict";
import worker, { parseAllowed, commandOf, formatReply } from "./cloudflare-worker.mjs";

const env = {
  TELEGRAM_BOT_TOKEN: "test-not-real",
  TELEGRAM_CHAT_ID: "123",
  TELEGRAM_EXTRA_CHAT_IDS: "456",
  TELEGRAM_WEBHOOK_SECRET: "test-secret",
};
test("parse allowed first and second users", () => {
  assert.deepEqual([...parseAllowed(env)], ["123", "456"]);
});
test("accept /start and /latest", () => {
  assert.equal(commandOf({text:"/start@solo_radar_hunter_bot"}),"/start");
  assert.equal(commandOf({text:"/latest"}),"/latest");
  assert.equal(commandOf({text:"hello"}),null);
});
test("summary from historical scan includes timestamp and candidate", () => {
  const state = {
    last_scan: "2026-11-20T05:00:00+00:00",
    topics: {
      "btt:123": {
        title: "[ANN] GPU Mining PoW Test Coin with KawPow",
        seen: "2026-11-20T05:00:00+00:00",
        links: {discord: "https://discord.gg/test", pool: "https://pool.example.com"},
      }
    },
  };
  const out = formatReply("/start", state, new Date("2026-11-20T06:00:00Z"));
  assert.match(out,/60 мин назад/);
  assert.match(out,/GPU Mining PoW Test Coin/);
  assert.match(out,/discord.gg\/test/);
  assert.match(out,/pool.example.com/);
});
test("health endpoint works without secrets", async () => {
  const res = await worker.fetch(new Request("https://example.workers.dev/health"), {});
  assert.equal(res.status, 200);
});
test("reject unauthenticated webhook", async () => {
  const req = new Request("https://example.workers.dev/webhook", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({message:{chat:{id:123},text:"/start"}})
  });
  const res = await worker.fetch(req, env);
  assert.equal(res.status, 403);
});
test("ignore unknown chat IDs", async () => {
  const req = new Request("https://example.workers.dev/webhook", {
    method:"POST",
    headers:{"Content-Type":"application/json","X-Telegram-Bot-Api-Secret-Token":"test-secret"},
    body: JSON.stringify({message:{chat:{id:999},text:"/start"}})
  });
  const res = await worker.fetch(req, env);
  assert.equal(res.status, 200);
});
