/**
 * SOLO Radar Telegram menu, Cloudflare Workers Free.
 * Commands and inline buttons use Telegram webhook (not GitHub cron).
 * Public snapshot: data/state.json. Never display project claims as verified.
 */
const STATE_URL = "https://raw.githubusercontent.com/Lepra186/solo-radar-free/main/data/state.json";
const PAGE_SIZE = 4;

export function parseAllowed(env) {
  return new Set([env.TELEGRAM_CHAT_ID, env.TELEGRAM_EXTRA_CHAT_IDS]
    .filter(Boolean).join(",").split(/[\s,;]+/)
    .filter(id => /^-?\d{1,20}$/.test(id)));
}

export function commandOf(message) {
  const first = String(message?.text || "").trim().split(/\s+/)[0].toLowerCase();
  const cmd = first.split("@")[0];
  return ["/start", "/latest", "/status", "/help"].includes(cmd) ? cmd : null;
}

const GPU = /\b(gpu|nvidia|amd|radeon|cuda|opencl|ethash|etchash|kawpow|progpow|fishhash|autolykos|equihash|verthash)\b/i;
const POW = /\b(pow|mining|mineable|minable|proof[- ]of[- ]work|gpu miner)\b/i;
const EXCLUDE = /\b(cpu[- ]only|randomx|yespower|airdrop|presale|ico|nft|testnet only)\b/i;
const SOFTWARE = /\b(miner\s*\d+(\.\d+)*|gpu mining software|software release)\b/i;
function isCandidate(title) {
  const s = String(title || "");
  return GPU.test(s) && POW.test(s) && !EXCLUDE.test(s) && !SOFTWARE.test(s);
}
function cleanUrl(raw) {
  if (typeof raw !== "string" || raw.length > 500) return null;
  try {
    const u = new URL(raw);
    if (u.protocol !== "https:" || u.username || u.password) return null;
    return u.toString();
  } catch { return null; }
}
function announcementUrl(key, item) {
  const url = cleanUrl(item?.url);
  if (url) return url;
  const id = /^btt:(\d+)$/.exec(key);
  return id ? "https://bitcointalk.org/index.php?topic=" + id[1] + ".0" : null;
}
const LINK_BUTTONS = [
  ["discord", "👥 Discord"],
  ["pool", "⛏️ Пул"],
  ["wallet", "💰 Кошелёк"],
  ["miner", "🖥️ Майнер"],
  ["explorer", "🔎 Блоки"],
  ["website", "🌐 Сайт"],
];
export function candidatesFromState(state) {
  return Object.entries(state?.topics || {})
    .filter(([, item]) => isCandidate(item?.title))
    .map(([key, item]) => ({key, item}))
    .sort((a, b) => String(b.item?.seen || "").localeCompare(String(a.item?.seen || "")));
}
function btn(text, callback_data) { return {text, callback_data}; }
function linkButton(text, url) { return {text, url}; }
function navRows() {
  return [
    [btn("🪙 Монеты на наблюдении", "watch:0")],
    [btn("🆕 Последние находки", "recent:0"), btn("📊 Статус", "status")],
    [btn("ℹ️ Справка", "help")],
  ];
}
function timeInfo(state, now) {
  const raw = String(state?.last_scan || "");
  const stamp = Date.parse(raw);
  const min = Number.isFinite(stamp) ? Math.max(0, Math.floor((now.getTime() - stamp)/60000)) : null;
  return {raw, text:min === null?"неизвестно":min+" мин назад", stale:min === null || min > 30};
}
function textFor(name) { return String(name || "").replace(/[\u0000-\u001f]/g, " ").slice(0, 95); }
export function renderMenu(view, state = {}, now = new Date()) {
  const list = candidatesFromState(state);
  const info = timeInfo(state, now);
  if (view === "status") {
    return {
      text: [
        "📊 SOLO RADAR • СТАТУС",
        "",
        "🟢 Telegram: отвечает через Cloudflare",
        "🕒 Сканирование: " + info.text + (info.stale?" ⚠️ устарело":""),
        "🔍 Записей в истории: " + Object.keys(state?.topics || {}).length,
        "🪙 GPU PoW на наблюдении: " + list.length,
        "",
        "Поиск монет выполняет GitHub Actions. Его запуск может задерживаться.",
      ].join("\n"),
      reply_markup: {inline_keyboard:[[btn("🔄 Обновить", "status")], [btn("🏠 Меню", "home")]]},
    };
  }
  if (view === "help") {
    return {
      text: [
        "ℹ️ SOLO RADAR • ПОМОЩЬ",
        "",
        "🪙 Монеты — архив отобранных GPU PoW-проектов",
        "🆕 Последние — недавно замеченные записи",
        "📊 Статус — время последнего сканирования",
        "🔗 В карточке проекта — ссылки на анонс, Discord, пул и другие ресурсы, если они сохранены.",
        "",
        "Команды: /start /latest /status /help",
        "⚠️ Найденные ссылки и заявления проектов не проверены на безопасность.",
      ].join("\n"),
      reply_markup:{inline_keyboard:[[btn("🏠 Меню","home")]]},
    };
  }
  if (view === "home") {
    return {
      text:[
        "📡 SOLO RADAR",
        "GPU PoW • NVIDIA / AMD",
        "",
        "🚀 Ранний майнинг • ⛏️ SOLO / пул",
        "🪙 Накопление монет для возможной продажи",
        "",
        "📂 Проектов на наблюдении: " + list.length,
        "🕒 Последний скан: " + info.text + (info.stale ? " ⚠️" : ""),
        "",
        "Выбери раздел кнопкой ниже.",
        "⚠️ Это поиск кандидатов, не гарантия прибыли или запуска mainnet.",
      ].join("\n"),
      reply_markup:{inline_keyboard:navRows()},
    };
  }
  const pageMatch = /^(watch|recent):(\d{1,3})$/.exec(view);
  if (pageMatch) {
    const isRecent = pageMatch[1] === "recent";
    const pool = isRecent ? list.filter(x => {
      const stamp = Date.parse(String(x.item?.seen || ""));
      return Number.isFinite(stamp) && 0 <= now.getTime()-stamp && now.getTime()-stamp <= 72*3600*1000;
    }) : list;
    const totalPages = Math.max(1, Math.ceil(pool.length / PAGE_SIZE));
    const page = Math.min(Number(pageMatch[2]), totalPages-1);
    const start = page * PAGE_SIZE;
    const rows = pool.slice(start, start+PAGE_SIZE).map((x, i) => {
      const globalIndex = list.findIndex(y => y.key === x.key);
      return [btn((start+i+1)+". "+textFor(x.item.title).slice(0, 45), "coin:"+globalIndex+":"+page+":"+(isRecent?"r":"w"))];
    });
    if (totalPages > 1) {
      const nav=[];
      if (page>0) nav.push(btn("◀️ Назад", (isRecent?"recent:":"watch:")+(page-1)));
      nav.push(btn((page+1)+"/"+totalPages,"noop"));
      if (page<totalPages-1) nav.push(btn("Вперёд ▶️", (isRecent?"recent:":"watch:")+(page+1)));
      rows.push(nav);
    }
    rows.push([btn("🏠 Главное меню","home")]);
    const heading = isRecent ? "🆕 ПОСЛЕДНИЕ НАХОДКИ" : "🪙 МОНИТОРИНГ GPU PoW";
    return {
      text: [heading, "", "Записей: "+pool.length+" • Страница "+(page+1)+"/"+totalPages,
        "🕒 Скан: "+info.text+(info.stale?" ⚠️":""),
        "", ...(pool.length?["Выбери монету, чтобы открыть ссылки:"]:["Сейчас в этом разделе записей нет."]),
        "", "⚠️ Записи не подтверждают возможность майнинга, листинг или рост цены."].join("\n"),
      reply_markup:{inline_keyboard:rows},
    };
  }
  const coinMatch = /^coin:(\d{1,5}):(\d{1,3}):([rw])$/.exec(view);
  if (coinMatch) {
    const index=Number(coinMatch[1]);
    const page=Number(coinMatch[2]);
    const back=coinMatch[3]==="r"?"recent:":"watch:";
    const result=list[index];
    if (!result) return renderMenu("watch:0",state,now);
    const {key,item}=result;
    const links = [];
    const announcement=announcementUrl(key,item);
    if (announcement) links.push(linkButton("📄 Анонс",announcement));
    for (const [kind,label] of LINK_BUTTONS) {
      const u=cleanUrl(item?.links?.[kind]);
      if (u) links.push(linkButton(label,u));
    }
    const rows=[];
    for (let i=0;i<links.length;i+=2) rows.push(links.slice(i,i+2));
    rows.push([btn("◀️ К списку", back+page),btn("🏠 Меню","home")]);
    return {
      text:[
        "🪙 КАРТОЧКА GPU PoW-ПРОЕКТА",
        "",
        textFor(item.title).slice(0,180),
        "",
        "📅 Впервые замечен: "+String(item.seen||"неизвестно").slice(0,19).replace("T"," ")+" UTC",
        "🔗 Ссылок найдено: "+links.length,
        "",
        "Открой первоисточник и проверь действительность пула, кошелька и Discord.",
        "⚠️ Поддержка GPU, premine, сложность сети и возможность продажи не проверены.",
      ].join("\n"),
      reply_markup:{inline_keyboard:rows},
    };
  }
  return renderMenu("home",state,now);
}

// Backwards-compatible export for offline regression tests.
export function formatReply(command,state,now=new Date()) {
  const view=command==="/status"?"status":command==="/help"?"help":"home";
  return renderMenu(view,state,now).text;
}
async function getState() {
  const res=await fetch(STATE_URL,{
    headers:{"User-Agent":"SOLO-Radar-Webhook/2.0"},
    cf:{cacheEverything:true,cacheTtl:45}
  });
  if (!res.ok) throw Error("GitHub state unavailable: "+res.status);
  return res.json();
}
async function api(env,method,payload) {
  const res=await fetch("https://api.telegram.org/bot"+env.TELEGRAM_BOT_TOKEN+"/"+method,{
    method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)
  });
  if (!res.ok) throw Error("Telegram "+method+" HTTP "+res.status);
  const body=await res.json();
  if (!body.ok) throw Error("Telegram "+method+" failed");
  return body;
}
export default {
  async fetch(request,env) {
    const path=new URL(request.url).pathname;
    if (path==="/health" && request.method==="GET") return new Response("SOLO Radar webhook online");
    if (path!=="/webhook") return new Response("Not found",{status:404});
    if (request.method!=="POST") return new Response("Method not allowed",{status:405});
    if (!env.TELEGRAM_WEBHOOK_SECRET || !env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) {
      return new Response("Not configured",{status:503});
    }
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token")!==env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("Forbidden",{status:403});
    }
    let update;
    try { update=await request.json(); } catch { return new Response("Invalid JSON",{status:400}); }
    const query=update?.callback_query;
    const message=update?.message;
    const chatId=String(query?.message?.chat?.id || message?.chat?.id || "");
    if (!parseAllowed(env).has(chatId)) {
      if (query?.id) {
        try {await api(env,"answerCallbackQuery",{callback_query_id:query.id,text:"Нет доступа"});}
        catch { /* Ignore unauthorized callbacks */ }
      }
      return new Response("OK");
    }
    const command=commandOf(message);
    let view = null;
    if (query) {
      view=String(query.data || "");
      if (view==="noop") {
        try {await api(env,"answerCallbackQuery",{callback_query_id:query.id});}
        catch { /* harmless */ }
        return new Response("OK");
      }
      if (!/^(home|status|help|watch:\d{1,3}|recent:\d{1,3}|coin:\d{1,5}:\d{1,3}:[rw])$/.test(view)) {
        return new Response("OK");
      }
    } else if (command) {
      view=command==="/status"?"status":command==="/help"?"help":"home";
    } else {
      return new Response("OK");
    }
    let state={};
    if (view!=="help") {
      try {state=await getState();}
      catch {console.error("Snapshot unavailable");}
    }
    const reply=renderMenu(view,state);
    try {
      if (query) {
        try {await api(env,"answerCallbackQuery",{callback_query_id:query.id});}
        catch { /* Continue editing menu */ }
        if (query.message?.message_id) {
          await api(env,"editMessageText",{
            chat_id:chatId,message_id:query.message.message_id,text:reply.text,
            reply_markup:reply.reply_markup,disable_web_page_preview:true
          });
        } else {
          await api(env,"sendMessage",{
            chat_id:chatId,text:reply.text,reply_markup:reply.reply_markup,
            disable_web_page_preview:true
          });
        }
      } else {
        await api(env,"sendMessage",{
          chat_id:chatId,text:reply.text,reply_markup:reply.reply_markup,
          disable_web_page_preview:true
        });
      }
    } catch (error) {
      console.error("Telegram menu delivery failed",String(error));
      return new Response("Delivery failed",{status:502});
    }
    return new Response("OK");
  }
};
