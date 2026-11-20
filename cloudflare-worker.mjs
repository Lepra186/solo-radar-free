/**
 * SOLO Radar command webhook on Cloudflare Workers Free.
 * The scanner still updates public data/state.json via GitHub Actions.
 * Configure Worker Secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
 * optional TELEGRAM_EXTRA_CHAT_IDS, TELEGRAM_WEBHOOK_SECRET.
 */
const STATE_URL = "https://raw.githubusercontent.com/Lepra186/solo-radar-free/main/data/state.json";

export function parseAllowed(env) {
  return new Set(
    [env.TELEGRAM_CHAT_ID, env.TELEGRAM_EXTRA_CHAT_IDS]
      .filter(Boolean).join(",").split(/[\s,;]+/)
      .filter((id) => /^-?\d{1,20}$/.test(id))
  );
}

export function commandOf(message) {
  const first = String(message?.text || "").trim().split(/\s+/)[0].toLowerCase();
  const cmd = first.split("@")[0];
  return ["/start", "/latest", "/status", "/help"].includes(cmd) ? cmd : null;
}

function isGpuPow(title) {
  const value = title.toLowerCase();
  const gpu = /\b(gpu|nvidia|amd|radeon|cuda|opencl|ethash|etchash|kawpow|progpow|fishhash|autolykos|equihash|verthash)\b/i.test(value);
  const pow = /\b(pow|mining|mineable|miner|proof[- ]of[- ]work)\b/i.test(value);
  const excluded = /\b(cpu[- ]only|randomx|yespower|airdrop|presale|ico|nft|testnet only)\b/i.test(value);
  return gpu && pow && !excluded;
}

function projectLinks(item) {
  const labels = [
    ["discord", "👥 Discord"], ["pool", "⛏️ Пул"],
    ["wallet", "💰 Кошелёк"], ["miner", "🖥️ Майнер"],
    ["explorer", "🔎 Обозреватель"], ["website", "🌐 Сайт"]
  ];
  return labels.filter(([key]) => typeof item?.links?.[key] === "string")
    .map(([key, label]) => {
      const url = item.links[key];
      return url.startsWith("https://") ? label + ": " + url : "";
    }).filter(Boolean).slice(0, 4);
}

export function formatReply(command, state, now = new Date()) {
  const stamp = String(state?.last_scan || "");
  const last = Date.parse(stamp);
  const ageMinutes = Number.isFinite(last)
    ? Math.max(0, Math.floor((now.getTime() - last) / 60000)) : null;
  const age = ageMinutes === null ? "нет данных" : ageMinutes + " мин назад";

  if (command === "/help") return [
    "📡 SOLO Radar — команды", "/start — обзор GPU PoW-проектов",
    "/latest — повторить обзор", "/status — состояние и возраст данных",
    "/help — справка", "",
    "Ответ приходит через webhook без ожидания GitHub Actions.",
    "Поиск новых монет выполняется отдельно по расписанию."
  ].join("\n");

  if (command === "/status") return [
    "📡 SOLO Radar — состояние", "Telegram webhook: работает",
    "Последнее сканирование: " + (stamp || "нет данных"),
    "Возраст данных: " + age,
    "Проектов в истории: " + Object.keys(state?.topics || {}).length,
    "Новую информацию сканирует GitHub Actions; его расписание может задерживаться."
  ].join("\n");

  const topics = Object.entries(state?.topics || {});
  const candidates = topics.filter(([, item]) => isGpuPow(String(item?.title || "")))
    .map(([key, item]) => ({ key, item }))
    .sort((a, b) => String(b.item?.seen || "").localeCompare(String(a.item?.seen || "")))
    .slice(0, 5);

  const lines = [
    "📡 SOLO Radar — GPU PoW",
    "NVIDIA и AMD, SOLO и обычный пул-майнинг.",
    "Последнее сканирование: " + (stamp || "нет данных") + " (" + age + ")",
    "Проектов в истории: " + topics.length, "",
    "📂 На наблюдении — записи прошлых проверок.",
    "Это НЕ подтверждённые свежие запуски и не совет инвестировать.", ""
  ];
  if (!candidates.length) lines.push("Подходящих записей в истории пока нет.");

  for (const [index, { key, item }] of candidates.entries()) {
    lines.push((index + 1) + ". " + String(item.title).slice(0, 150));
    if (typeof item.url === "string" && item.url.startsWith("https://")) {
      lines.push(item.url);
    } else if (key.startsWith("btt:") && /^\d+$/.test(key.slice(4))) {
      lines.push("https://bitcointalk.org/index.php?topic=" + key.slice(4) + ".0");
    }
    lines.push(...projectLinks(item), "");
  }
  lines.push("⚠️ Премайн, GPU-совместимость и ликвидность не подтверждены.");
  return lines.join("\n").slice(0, 3900);
}

async function getState() {
  const response = await fetch(STATE_URL, {
    headers: { "User-Agent": "SOLO-Radar-Webhook/1.0" },
    cf: { cacheEverything: true, cacheTtl: 45 }
  });
  if (!response.ok) throw new Error("Snapshot HTTP " + response.status);
  return response.json();
}

async function sendTelegram(env, chatId, message) {
  const response = await fetch(
    "https://api.telegram.org/bot" + env.TELEGRAM_BOT_TOKEN + "/sendMessage",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: chatId, text: message, disable_web_page_preview: true
      })
    }
  );
  if (!response.ok) throw new Error("Telegram send HTTP " + response.status);
  if (!(await response.json()).ok) throw new Error("Telegram sendMessage failed");
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === "/health" && request.method === "GET") {
      return new Response("SOLO Radar webhook online");
    }
    if (path !== "/webhook") return new Response("Not found", { status: 404 });
    if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });
    if (!env.TELEGRAM_WEBHOOK_SECRET || !env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) {
      return new Response("Not configured", { status: 503 });
    }
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("Forbidden", { status: 403 });
    }
    let update;
    try { update = await request.json(); }
    catch { return new Response("Invalid JSON", { status: 400 }); }
    const msg = update?.message;
    const chatId = String(msg?.chat?.id || "");
    const command = commandOf(msg);
    if (!command || !parseAllowed(env).has(chatId)) return new Response("OK");

    let state = {};
    if (command !== "/help") {
      try { state = await getState(); }
      catch { console.error("Snapshot unavailable"); }
    }
    try {
      await sendTelegram(env, chatId, formatReply(command, state));
    } catch (error) {
      console.error("Telegram delivery failed", String(error));
      return new Response("Delivery failed", { status: 502 });
    }
    return new Response("OK");
  }
};
