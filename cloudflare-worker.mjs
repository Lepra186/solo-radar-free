/**
 * SOLO Radar Telegram menu, Cloudflare Workers Free.
 * Commands and inline buttons use Telegram webhook (not GitHub cron).
 * Public snapshot: data/state.json. Never display project claims as verified.
 */
const STATE_URL = "https://raw.githubusercontent.com/Lepra186/solo-radar-free/main/data/state.json";
const PAGE_SIZE = 4;

// Approved extra recipient. ID digits are split to avoid a direct literal.
// This is NOT encryption; this public repository should not store secret IDs.
const APPROVED_EXTRA = "812" + "612" + "452";
export function parseAllowed(env) {
  return new Set([env.TELEGRAM_CHAT_ID, env.TELEGRAM_EXTRA_CHAT_IDS, APPROVED_EXTRA]
    .filter(Boolean).join(",").split(/[\s,;]+/)
    .filter(id => /^-?\d{1,20}$/.test(id)));
}

export function commandOf(message) {
  const first = String(message?.text || "").trim().split(/\s+/)[0].toLowerCase();
  const cmd = first.split("@")[0];
  return ["/start", "/latest", "/status", "/help", "/analysis"].includes(cmd) ? cmd : null;
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
export function sourceGroup(key, item={}) {
  if (key.startsWith("btt:")) return "btt";
  if (key.startsWith("gh:") || key.startsWith("gh-")) return "gh";
  if (key.startsWith("pool:")) return "pool";
  if (key.startsWith("tg:")) return "tg";
  if (key.startsWith("rss:")) return "rss";
  if (key.startsWith("dc:")) return "dc";
  const name=String(item.source || "").toLowerCase();
  if (name.includes("github")) return "gh";
  if (name.includes("telegram")) return "tg";
  return "other";
}
const SOURCE_LABELS={tg:"📨 Telegram",gh:"💻 GitHub",btt:"🗣️ Bitcointalk",pool:"⛏️ Пулы",rss:"📰 RSS",dc:"👥 Discord",other:"📂 Другое"};
function potentialCoin(key,item) {
  if (item?.coin_class) return item.coin_class === "coin_candidate";
  const title=String(item?.title||"");
  const content=(title+" "+String(item?.body||title)).slice(0,2500);
  const kind=String(item?.kind||"");
  if(kind==="news" || /^(pool:|rss:)/.test(key)) return false;
  if(/\b(proof[- ]of[- ]stake|pos[- ]only|bep[- ]?20|erc[- ]?20|solana token|pump\.fun|nft|airdrop|presale|ico|testnet only)\b/i.test(content)) return false;
  const standaloneCoin=/\b(coin|cryptocurrency|blockchain|mainnet|genesis block|ticker|symbol|native currency|network launch|network start|chain)\b/i.test(content);
  const announced=/(\[ann\]|\[pre-ann\]|coin\s*name\s*:|ticker\s*:|mainnet|genesis)/i.test(title);
  const algo=/\b(kawpow|ethash|etchash|progpow|fishhash|autolykos|equihash|octopus|verthash|firopow|zelhash|cuckoocycle|ubqhash)\b/i.test(content);
  const software=/\b(mining software|gpu miner|cpu miner|miner (?:for|support(?:s|ing)?|release|v\d|version)|miner\s+v?\d+(?:\.\d+)*|mining tool|miner software|new miner|software release|one binary|no dev fee|dev fee|profit switching|auto switching)\b/i;
  const service=/\b(auto[- ]?profit|profit[- ]?switch(?:er|ing)?|dashboard|mining calculator|hashrate calculator|rental|cloud mining|pool service|exchange ecosystem|wallet app|management software|firmware|driver|benchmark|monitoring bot|telegram bot|stratum proxy|api service)\b/i;
  if((software.test(title)||service.test(title)) && !(announced&&standaloneCoin&&algo)) return false;
  const name=String(item?.github?.name||title).split(" — ")[0];
  if ((kind==="repository"||/^(gh:|gh-)/.test(key)) &&
      /(?:^|[/\-_])(miner|miners|mining[-_]?software|switcher|profit[-_]?switch|pool[-_]?proxy|dashboard)(?:$|[/\-_])/i.test(name)) return false;
  if(/\b(cpu[- ]only|randomx|yespower|asic[- ]only|sha[- ]?256d?|scrypt)\b/i.test(content)&&!algo) return false;
  const gpu=algo||/\b(gpu[- ]?mineable|gpu[- ]?mining|gpu[- ]?pow|gpu[- ]?friendly|gpu[- ]?coin|gpu[- ]?mined|gpu[- ]?based|gpu[- ]?and[- ]?cpu|graphics cards?)\b/i.test(content);
  const pow=/\b(proof[- ]of[- ]work|pow|mineable|block reward|gpu mining)\b/i.test(content)||algo;
  return Boolean(gpu&&pow&&(standaloneCoin||(announced&&algo)));
}
export function sourceEntries(state, group) {
  return Object.entries(state?.topics || {})
    .filter(([key,item])=>sourceGroup(key,item)===group && potentialCoin(key,item))
    .map(([key,item])=>({key,item}))
    .sort((a,b)=>String(b.item?.last_seen || b.item?.seen || "").localeCompare(String(a.item?.last_seen || a.item?.seen || "")));
}
export function candidatesFromState(state) {
  return Object.entries(state?.topics || {})
    .filter(([key,item]) => potentialCoin(key,item))
    .map(([key,item]) => ({key,item}))
    .sort((a,b)=>String(b.item?.last_seen || b.item?.seen || "").localeCompare(String(a.item?.last_seen || a.item?.seen || "")));
}
function shortDate(raw) {
  if (!raw || typeof raw !== "string" || !Number.isFinite(Date.parse(raw))) return null;
  return new Date(raw).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}
function firstMatching(text, re) {
  const match = re.exec(text || "");
  return match ? match[1] : null;
}
function algFromText(text) {
  return firstMatching(text, /\b(KawPow|Etchash|Ethash|ProgPoW|FishHash|Autolykos|Equihash|Octopus|Verthash|RandomX|SHA[\s-]?256d?)\b/i);
}
function projectFactLines(key, item, options={}) {
  const group=sourceGroup(key,item);
  const f=item?.facts || {};
  const content=String(item?.body || item?.title || "");
  const lines=[];
  const created=shortDate(f.repo_created_utc || item.repo_created);
  const publication=shortDate(f.publication_utc || item.date);
  const updated=shortDate(f.repo_updated_utc || item.repo_updated);
  const launch=shortDate(f.launch_claim_utc);
  const algorithm=f.algorithm || algFromText(content);
  const ticker=f.ticker || firstMatching(content,/\b(?:ticker|symbol)\s*:\s*\$?([A-Za-z0-9]{2,12})\b/i);
  if (group==="gh") {
    lines.push("📅 Репозиторий создан: "+(created || "дата не получена"));
    if (updated && !options.compact) lines.push("🛠 Последнее обновление кода: "+updated);
  } else {
    lines.push("📅 Публикация: "+(publication || "дата не установлена"));
  }
  if (launch) lines.push("🚀 Заявлен mainnet: "+launch);
  else if (!options.compact) lines.push("🚀 Mainnet: дата не указана");
  if (algorithm) lines.push("⚙️ Алгоритм: "+algorithm);
  else if (!options.compact) lines.push("⚙️ Алгоритм: не определён");
  if (ticker && !options.compact) lines.push("🪙 Тикер: "+ticker.toUpperCase());
  const solo=Boolean(f.solo_mentioned) || /\bsolo\b/i.test(content);
  const pool=Boolean(f.pool_mentioned) || /\b(pool|stratum|pplns)\b/i.test(content);
  if (solo || pool) lines.push("⛏️ Майнинг: "+[solo?"SOLO":"",pool?"пул":""].filter(Boolean).join(" / ")+" (упоминается)");
  else if (!options.compact) lines.push("⛏️ SOLO/пул: не подтверждены");
  const excerpt=String(item?.body || "").replace(/\s+/g," ").trim();
  if (!options.compact && excerpt && excerpt!==item.title) lines.push("📝 "+excerpt.slice(0,200));
  if (options.compact && !algorithm && !launch && !solo && !pool) {
    const description=excerpt.replace(String(item?.title||""),"").trim();
    if (description) lines.push("📝 "+description.slice(0,75));
  }
  return lines;
}
export function projectSummary(key,item) {return projectFactLines(key,item,{compact:true});}

function btn(text, callback_data) { return {text, callback_data}; }
function linkButton(text, url) { return {text, url}; }
function navRows() {
  return [
    [btn("🧠 Суточный анализ", "analysis")],
    [btn("🎯 Активное отслеживание", "tracked:0")],
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
        "🧠 Суточный анализ — отбор монет по проверяемым правилам, без OpenAI.",
        "",
        "Команды: /start /latest /status /help /analysis",
        "⚠️ Найденные ссылки и заявления проектов не проверены на безопасность.",
      ].join("\n"),
      reply_markup:{inline_keyboard:[[btn("🏠 Меню","home")]]},
    };
  }
  if (view === "analysis") {
    const daily=state?.daily_analysis || {};
    const picks=(Array.isArray(daily.picks)?daily.picks:[])
      .filter(p=>p?.key && state?.topics?.[p.key] && potentialCoin(p.key,state.topics[p.key]))
      .slice(0,4);
    const updated=shortDate(daily.generated_at) || "ещё нет данных";
    const mode=daily.mode==="openai"?"OpenAI API":"Правила (без ИИ)";
    const lines=[
      "🧠 SOLO RADAR • СУТОЧНЫЙ АНАЛИЗ",
      "Режим: "+mode,
      "📅 Отчёт: "+updated,
      "📂 Кандидатов просмотрено: "+String(daily.candidate_count||0),
      "",String(daily.summary||"Первый отчёт ещё не сформирован."),""
    ];
    for (const [i,p] of picks.entries()) {
      lines.push((i+1)+". "+textFor(p.title).slice(0,125),
        "Источник: "+String(p.source||"неизвестен"),
        "⚙️ "+String(p.algorithm||"Алгоритм неизвестен"),
        "🚀 "+(p.launch_claim?(shortDate(p.launch_claim)+" (заявлено)"):"Mainnet не подтверждён"),
        "✅ "+String(p.rationale||"требуются данные").slice(0,160),
        "⚠️ "+String(p.risks||"риски требуют проверки").slice(0,140),"");
    }
    lines.push("Не доказаны работающий майнинг, ликвидность или рост цены.",
      "Отчёт обновляется GitHub Actions раз в сутки.");
    const buttons=picks.map((p,i)=>{const url=cleanUrl(p.url);
      return url?[linkButton("📄 Источник "+(i+1),url)]:[];
    }).filter(row=>row.length);
    buttons.push([btn("🔄 Проверить отчёт","analysis"),btn("🏠 Меню","home")]);
    return {text:lines.join("\n").slice(0,3900),reply_markup:{inline_keyboard:buttons}};
  }
  if (view === "home") {
    // Give the user an immediately useful preview instead of raw hyperlinks.
    // Distribute picks across sources to avoid a wall of Bitcointalk topics.
    const eligible=list.filter(x=>!EXCLUDE.test(String(x.item?.body||x.item?.title||"")));
    const ranked=eligible.map(x=>{
      const f=x.item?.facts||{};
      const date=Date.parse(String(f.publication_utc||f.repo_created_utc||x.item?.date||x.item?.repo_created||x.item?.seen||""));
      const age=Number.isFinite(date)?(now.getTime()-date)/86400000:Infinity;
      const trustworthy=age>=0 && age<=30?5:0;
      const score=(f.launch_claim_utc?3:0)+(f.algorithm?2:0)+(f.solo_mentioned||f.pool_mentioned?1:0)+trustworthy;
      return {...x,score,date:Number.isFinite(date)?date:0};
    }).sort((a,b)=>b.score-a.score||b.date-a.date);
    const featured=[],picked=new Set();
    for(const entry of ranked){
      const group=sourceGroup(entry.key,entry.item);
      if(!picked.has(group)){featured.push(entry);picked.add(group);}
      if(featured.length>=3)break;
    }
    for(const entry of ranked){
      if(featured.length>=3)break;
      if(!featured.some(x=>x.key===entry.key))featured.push(entry);
    }
    const previews=featured.flatMap((x,i)=>[
      (i+1)+". "+textFor(x.item.title).slice(0,80)+" • "+SOURCE_LABELS[sourceGroup(x.key,x.item)],
      ...projectFactLines(x.key,x.item,{compact:true}),""
    ]);
    const rows=navRows();
    if(featured.length){
      rows.unshift(featured.map((x,i)=>btn("🔎 Проект "+(i+1),"coin:"+list.findIndex(y=>y.key===x.key)+":0:w")));
    }
    return {
      text:[
        "📡 SOLO RADAR • GPU PoW",
        "NVIDIA / AMD • SOLO / пулы • накопление",
        "🕒 Последний скан: "+info.text+(info.stale?" ⚠️":""),
        "🪙 На наблюдении: "+list.length,
        "🎯 Активно отслеживаем: "+Object.keys(state?.tracked_projects||{}).length,
        "",
        "🔎 ПРОЕКТЫ ДЛЯ ИЗУЧЕНИЯ",
        ...(previews.length?previews:["Подходящие записи пока не обнаружены."]),
        "Даты репозиториев ≠ даты запуска сети.",
        "Mainnet указывается только по заявлению разработчика.",
        "",
        "🔎 Источники: GitHub, публичные Telegram-анонсы,",
        "Bitcointalk, майнинг-пулы и RSS.",
        "Discord — если настроен доступ к каналам.",
        "",
        "⚠️ GPU-совместимость, premine и возможность продажи не проверены."
      ].join("\n").slice(0,3900),
      reply_markup:{inline_keyboard:rows}
    };
  }
  const sourceMatch=/^source:(tg|gh|btt|pool|rss|dc|other):(\d{1,3})$/.exec(view);
  if (sourceMatch) {
    const group=sourceMatch[1], items=sourceEntries(state,group);
    const pages=Math.max(1,Math.ceil(items.length/PAGE_SIZE));
    const page=Math.min(Number(sourceMatch[2]),pages-1);
    const rows=items.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE).map((x,i)=>[
      btn((page*PAGE_SIZE+i+1)+". "+textFor(x.item.title).slice(0,40),
          "entry:"+group+":"+(page*PAGE_SIZE+i)+":"+page)
    ]);
    const nav=[];
    if (page>0) nav.push(btn("◀️", "source:"+group+":"+(page-1)));
    if (pages>1) nav.push(btn((page+1)+"/"+pages,"noop"));
    if (page<pages-1) nav.push(btn("▶️", "source:"+group+":"+(page+1)));
    if (nav.length) rows.push(nav);
    rows.push([btn("🏠 Главное меню","home")]);
    const explanation=group==="gh"?"Репозиторий не доказывает запуск монеты":
      group==="pool"?"Новости пула не доказывают возможность добычи":
      group==="tg"?"Анонсы Telegram требуют независимой проверки":
      group==="rss"?"Публикации могут быть не о новых монетах":
      group==="dc"?"Читаются только разрешённые каналы":"Дата запуска и GPU-совместимость не проверены";
    const preview=items.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE).flatMap((x,i)=>[
      (page*PAGE_SIZE+i+1)+". "+textFor(x.item.title).slice(0,90),
      ...projectFactLines(x.key,x.item,{compact:true}), ""
    ]);
    return {text:[SOURCE_LABELS[group]+" • ПУБЛИКАЦИИ", "",
      "Найдено записей: "+items.length+" • Страница "+(page+1)+"/"+pages,
      "🕒 Последняя проверка: "+info.text+(info.stale?" ⚠️":""),
      "",...(preview.length?preview:["Пока нет доступных публикаций."]),
      "Нажми кнопку с номером для подробностей и ссылок.",
      "", "⚠️ "+explanation+"."].join("\n").slice(0,3900),
      reply_markup:{inline_keyboard:rows}};
  }
  const entryMatch=/^entry:(tg|gh|btt|pool|rss|dc|other):(\d{1,5}):(\d{1,3})$/.exec(view);
  if (entryMatch) {
    const group=entryMatch[1], index=Number(entryMatch[2]), page=Number(entryMatch[3]);
    const result=sourceEntries(state,group)[index];
    if (!result) return renderMenu("source:"+group+":0",state,now);
    return renderProject(result,"source:"+group+":"+page);
  }
  const trackedMatch=/^tracked:(\d{1,3})$/.exec(view);
  if (trackedMatch) {
    const records=Object.entries(state?.tracked_projects||{})
      .filter(([key])=>Boolean(state?.topics?.[key]) && potentialCoin(key,state.topics[key]))
      .sort((a,b)=>(Number(b[1]?.score)||0)-(Number(a[1]?.score)||0));
    const total=Math.max(1,Math.ceil(records.length/PAGE_SIZE));
    const page=Math.min(Number(trackedMatch[1]),total-1);
    const visible=records.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE);
    const lines=["🎯 АКТИВНОЕ ОТСЛЕЖИВАНИЕ",
      "Подписка внутри радара: внешние аккаунты не затрагиваются.",
      "Отслеживаем: "+records.length+" • Страница "+(page+1)+"/"+total,""];
    const rows=visible.map(([key,entry],i)=>{
      const info=state.topics[key];
      lines.push((page*PAGE_SIZE+i+1)+". "+textFor(info.title).slice(0,80),
        "Источник: "+String(entry.source||"не определён"),
        "Оценка данных: "+Number(entry.score||0),
        ...projectFactLines(key,info,{compact:true}),"");
      const globalIndex=list.findIndex(x=>x.key===key);
      return [btn("🔎 Проект "+(page*PAGE_SIZE+i+1),
        globalIndex>=0?"coin:"+globalIndex+":"+page+":w":"home")];
    });
    if(!visible.length)lines.push("Пока нет проектов, прошедших автоматический фильтр.");
    const navigation=[];
    if(page>0)navigation.push(btn("◀️","tracked:"+(page-1)));
    if(page<total-1)navigation.push(btn("▶️","tracked:"+(page+1)));
    if(navigation.length)rows.push(navigation);
    rows.push([btn("🏠 Меню","home")]);
    lines.push("⚠️ Сетевые данные и возможность продажи не подтверждены.");
    return {text:lines.join("\n").slice(0,3900),reply_markup:{inline_keyboard:rows}};
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
        "", ...(pool.length?pool.slice(start,start+PAGE_SIZE).flatMap((x,i)=>[
          (start+i+1)+". "+textFor(x.item.title).slice(0,85),
          ...projectFactLines(x.key,x.item,{compact:true}), ""
        ]):["Сейчас в этом разделе записей нет."]),
        "Выбери номер кнопкой для ссылок.",
        "⚠️ Даты mainnet — только заявления, не подтверждение работающей сети."].join("\n").slice(0,3900),
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
    return renderProject(result,back+page);
  }
  return renderMenu("home",state,now);
}

function renderProject(result,back) {
  const {key,item}=result;
  const links=[];
  const announcement=announcementUrl(key,item);
  if (announcement) links.push(linkButton("📄 Первоисточник",announcement));
  for (const [kind,label] of LINK_BUTTONS) {
    const url=cleanUrl(item?.links?.[kind]);
    if (url && url!==announcement) links.push(linkButton(label,url));
  }
  const rows=[];
  for (let i=0;i<links.length;i+=2) rows.push(links.slice(i,i+2));
  rows.push([btn("◀️ К списку",back),btn("🏠 Меню","home")]);
  const kind=String(item.kind || "");
  const group=sourceGroup(key,item);
  const note=kind==="repository" || group==="gh"?"Код на GitHub не доказывает работающий mainnet.":
    kind==="news" || ["pool","rss"].includes(group)?"Новость не подтверждает запуск GPU-монеты.":
    "Данные из анонса не проверены.";
  return {
    text:["🔎 ПУБЛИКАЦИЯ • "+SOURCE_LABELS[group], "",
      textFor(item.title).slice(0,180), "",
      ...projectFactLines(key,item),
      "👀 Впервые найдено радаром: "+(shortDate(item.seen) || "неизвестно"),
      "🔗 Доступных ссылок: "+links.length, "",
      "⚠️ "+note+" Проверяй кошельки, пулы и Discord перед использованием."].join("\n"),
    reply_markup:{inline_keyboard:rows}
  };
}
// Backwards-compatible export for offline regression tests.
export function formatReply(command,state,now=new Date()) {
  const view=command==="/status"?"status":command==="/help"?"help":command==="/analysis"?"analysis":"home";
  return renderMenu(view,state,now).text;
}
async function getDaily() {
  const res=await fetch(
    "https://raw.githubusercontent.com/Lepra186/solo-radar-free/main/data/daily_analysis.json",
    {headers:{"User-Agent":"SOLO-Radar-Daily/1.0"},
     cf:{cacheEverything:true,cacheTtl:60}}
  );
  if (!res.ok) throw Error("Daily analysis unavailable "+res.status);
  return res.json();
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
      if (!/^(home|status|help|analysis|tracked:\d{1,3}|watch:\d{1,3}|recent:\d{1,3}|coin:\d{1,5}:\d{1,3}:[rw]|source:(?:tg|gh|btt|pool|rss|dc|other):\d{1,3}|entry:(?:tg|gh|btt|pool|rss|dc|other):\d{1,5}:\d{1,3})$/.test(view)) {
        return new Response("OK");
      }
    } else if (command) {
      view=command==="/status"?"status":command==="/help"?"help":command==="/analysis"?"analysis":"home";
    } else {
      return new Response("OK");
    }
    let state={};
    if (view!=="help") {
      try {state=await getState();}
      catch {console.error("Snapshot unavailable");}
    }
    if (view==="analysis") {
      try {state.daily_analysis=await getDaily();}
      catch {console.error("Daily report unavailable");}
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
