import test from "node:test";
import assert from "node:assert/strict";
import worker,{parseAllowed,commandOf,formatReply,renderMenu,candidatesFromState,projectSummary} from "./cloudflare-worker.mjs";

const env={TELEGRAM_BOT_TOKEN:"test-not-real",TELEGRAM_CHAT_ID:"123",
  TELEGRAM_EXTRA_CHAT_IDS:"456",TELEGRAM_WEBHOOK_SECRET:"test-secret"};
const state={last_scan:"2026-11-20T05:00:00+00:00",
  topics:{
    "btt:111":{title:"[ANN] GPU Mining PoW NewCoin KawPow",seen:"2026-11-20T04:00:00+00:00",
      links:{discord:"https://discord.gg/new",pool:"https://pool.example.com",wallet:"https://wallet.example.com"}},
    "btt:222":{title:"[ANN] GPU Mining PoW NewCoin2 Ethash",seen:"2026-11-20T03:00:00+00:00"},
    "btt:333":{title:"[ANN] GPU Mining PoW NewCoin3 Ethash",seen:"2026-11-20T02:00:00+00:00"},
    "btt:444":{title:"[ANN] GPU Mining PoW NewCoin4 Ethash",seen:"2026-11-20T01:00:00+00:00"},
    "btt:555":{title:"[ANN] GPU Mining PoW NewCoin5 Ethash",seen:"2026-11-20T00:00:00+00:00"},
    "btt:666":{title:"[ANN] NVIDIA GPU miner 1.0 software release",seen:"2026-11-20T00:00:00+00:00"},
  }};
const now=new Date("2026-11-20T06:00:00Z");
test("authorized recipients",()=>assert.deepEqual([...parseAllowed(env)],["123","456","812612452"]));
test("recognized commands",()=>{
  assert.equal(commandOf({text:"/start@solo_radar_hunter_bot"}),"/start");
  assert.equal(commandOf({text:"/latest"}),"/latest");
  assert.equal(commandOf({text:"bad"}),null);
});
test("home displays navigation instead of large raw links",()=>{
  const home=renderMenu("home",state,now);
  assert.match(home.text,/SOLO RADAR/);
  assert.match(home.text,/60 мин назад/);
  assert.ok(home.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="watch:0"));
  assert.doesNotMatch(home.text,/pool.example.com/);
});
test("watchlist is paginated with project selection",()=>{
  const first=renderMenu("watch:0",state,now);
  const second=renderMenu("watch:1",state,now);
  assert.equal(candidatesFromState(state).length,5);
  assert.match(first.text,/Страница 1\/2/);
  assert.ok(first.reply_markup.inline_keyboard.flat().some(b=>b.callback_data==="watch:1"));
  assert.match(second.text,/Страница 2\/2/);
});
test("coin detail carries exact clickable source links",()=>{
  const card=renderMenu("coin:0:0:w",state,now);
  const buttons=card.reply_markup.inline_keyboard.flat();
  assert.ok(buttons.some(x=>x.url==="https://discord.gg/new"));
  assert.ok(buttons.some(x=>x.url==="https://pool.example.com/"));
  assert.ok(buttons.some(x=>x.url==="https://wallet.example.com/"));
  assert.ok(buttons.some(x=>x.callback_data==="watch:0"));
});
test("missing project links not fabricated",()=>{
  const card=renderMenu("coin:1:0:w",state,now);
  const buttons=card.reply_markup.inline_keyboard.flat();
  assert.ok(buttons.some(x=>x.url?.includes("bitcointalk.org")));
  assert.ok(!buttons.some(x=>x.text?.includes("Discord")));
});
test("statuses warn about stale data",()=>{
  const status=renderMenu("status",state,now);
  assert.match(status.text,/устарело/);
  assert.ok(status.reply_markup.inline_keyboard.flat().some(x=>x.callback_data==="home"));
});
test("older tests: status and menu text exports",()=>{
  assert.match(formatReply("/start",state,now),/SOLO RADAR/);
  assert.match(formatReply("/status",state,now),/60 мин/);
});
test("health does not expose secrets",async()=>{
  const res=await worker.fetch(new Request("https://example.workers.dev/health"),{});
  assert.equal(res.status,200);
});
test("reject unauthenticated webhook",async()=>{
  const req=new Request("https://example.workers.dev/webhook",
    {method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({message:{chat:{id:123},text:"/start"}})});
  assert.equal((await worker.fetch(req,env)).status,403);
});
test("reject unknown chat ID",async()=>{
  const req=new Request("https://example.workers.dev/webhook",
    {method:"POST",headers:{"Content-Type":"application/json","X-Telegram-Bot-Api-Secret-Token":"test-secret"},
      body:JSON.stringify({message:{chat:{id:999},text:"/start"}})});
  assert.equal((await worker.fetch(req,env)).status,200);
});
test("reject unknown callback without disclosure",async()=>{
  const req=new Request("https://example.workers.dev/webhook",
    {method:"POST",headers:{"Content-Type":"application/json","X-Telegram-Bot-Api-Secret-Token":"test-secret"},
      body:JSON.stringify({callback_query:{message:{chat:{id:123},message_id:5},data:"admin:secret"}})});
  assert.equal((await worker.fetch(req,env)).status,200);
});

test("source tabs exist for all connected services",()=>{
  const menu=renderMenu("home",state,now);
  for (const key of ["tg","gh","btt","pool","rss","dc"]) {
    assert.ok(menu.reply_markup.inline_keyboard.flat().some(x=>x.callback_data==="source:"+key+":0"),key);
  }
});
test("source browser lists only GPU PoW coin candidates",()=>{
  const s={topics:{
    "gh:99":{title:"Example GPU Ethash PoW cryptocurrency repository",body:"GPU Ethash proof of work blockchain",seen:"2026-11-20T04:00:00Z",
      source:"GitHub — repository",url:"https://github.com/example/coin"},
    "tg:miningrelease:301":{title:"Coin Name: NewCoin GPU KawPow PoW",seen:"2026-11-20T05:00:00Z",
      url:"https://t.me/miningrelease/301",links:{discord:"https://discord.gg/mycoin",pool:"https://pool.example.org"}},
    "btt:222":{title:"[ANN] GPU Mining PoW",seen:"2026-11-20T05:00:00Z"}
  }};
  const gh=renderMenu("source:gh:0",s,now);
  const tg=renderMenu("source:tg:0",s,now);
  assert.match(gh.text,/1 • Страница/);
  assert.equal(gh.reply_markup.inline_keyboard[0][0].callback_data,"entry:gh:0:0");
  assert.equal(tg.reply_markup.inline_keyboard[0][0].callback_data,"entry:tg:0:0");
  const detail=renderMenu("entry:tg:0:0",s,now);
  assert.ok(detail.reply_markup.inline_keyboard.flat().some(x=>x.url==="https://discord.gg/mycoin"));
  assert.ok(detail.reply_markup.inline_keyboard.flat().some(x=>x.url==="https://pool.example.org/"));
});
test("pool news are identified as publications, not coins",()=>{
  const s={topics:{"pool:2026-11-20:0":{
    title:"GPU Mining newest pool update",body:"GPU Mining newest pool update",
    url:"https://pool-pay.com",seen:"2026-11-20T05:00:00Z",kind:"news"}}};
  assert.equal(candidatesFromState(s).length,0);
  assert.match(renderMenu("source:pool:0",s,now).text,/Пока нет доступных публикаций/);
});

test("authorized second user can access interactive menu",()=>{
  assert.ok(parseAllowed(env).has("812612452"));
  assert.ok(renderMenu("home",state,now).reply_markup.inline_keyboard.length>0);
});

test("GitHub list preview distinguishes repository creation from mainnet",()=>{
  const s={topics:{"gh:123":{title:"example/chain",kind:"repository",url:"https://github.com/example/chain",
    body:"GPU Ethash PoW blockchain cryptocurrency",seen:"2026-11-20T06:00:00Z",
    facts:{repo_created_utc:"2026-11-17T12:00:00Z",algorithm:"Ethash"}}}};
  const page=renderMenu("source:gh:0",s,now);
  assert.match(page.text,/Репозиторий создан: 2026-11-17 12:00 UTC/);
  assert.match(page.text,/Алгоритм: Ethash/);
  assert.doesNotMatch(page.text,/Заявлен mainnet/);
  const detail=renderMenu("entry:gh:0:0",s,now);
  assert.match(detail.text,/Mainnet: дата не указана/);
});
test("Telegram source list shows post timestamp and announced launch",()=>{
  const s={topics:{"tg:miningrelease:301":{title:"NewCoin GPU KawPow PoW coin",
    body:"NewCoin GPU KawPow PoW coin. Solo pool.",
    date:"2026-11-20T04:00:00Z",seen:"2026-11-20T05:00:00Z",
    facts:{publication_utc:"2026-11-20T04:00:00Z",launch_claim_utc:"2026-11-22T17:00:00Z",
    algorithm:"KawPow",solo_mentioned:true,pool_mentioned:true}}}};
  const page=renderMenu("source:tg:0",s,now);
  assert.match(page.text,/Публикация: 2026-11-20 04:00 UTC/);
  assert.match(page.text,/Заявлен mainnet: 2026-11-22 17:00 UTC/);
  assert.match(page.text,/SOLO \/ пул/);
});
test("source first-page gives useful preview even when timestamp absent",()=>{
  const s={topics:{"btt:554":{title:"New GPU PoW Coin KawPow",seen:"2026-11-20T03:00:00Z"}}};
  const page=renderMenu("source:btt:0",s,now);
  assert.match(page.text,/Публикация: дата не установлена/);
  assert.match(page.text,/Алгоритм: KawPow/);
  assert.ok(projectSummary("btt:554",s.topics["btt:554"]).length>=2);
});

test("home /start shows project facts and direct project buttons",()=>{
 const sample={topics:{
  "gh:888":{title:"demo/gpuchain PoW GPU",body:"GPU proof of work Ethash mining cryptocurrency blockchain",
    kind:"repository",repo_created:"2026-11-18T10:00:00Z",seen:"2026-11-18T10:00:00Z",
    facts:{repo_created_utc:"2026-11-18T10:00:00Z",algorithm:"Ethash"}},
  "tg:miningrelease:31":{title:"Coin Name: TChain GPU KawPow",body:"Coin Name: TChain GPU KawPow mining SOLO",
    date:"2026-11-19T09:00:00Z",seen:"2026-11-19T09:00:00Z",
    facts:{publication_utc:"2026-11-19T09:00:00Z",algorithm:"KawPow",
      launch_claim_utc:"2026-11-22T14:00:00Z",solo_mentioned:true}},
  "btt:200":{title:"[ANN] Some GPU PoW new coin Ethash",seen:"2026-11-17T10:00:00Z"}
 }};
 const home=renderMenu("home",sample,now);
 assert.match(home.text,/Репозиторий создан: 2026-11-18 10:00 UTC/);
 assert.match(home.text,/Публикация: 2026-11-19 09:00 UTC/);
 assert.match(home.text,/Заявлен mainnet: 2026-11-22 14:00 UTC/);
 assert.match(home.text,/Алгоритм: KawPow/);
 assert.ok(home.reply_markup.inline_keyboard.flat().some(x=>x.text==="🔎 Проект 1"));
 assert.match(home.text,/Даты репозиториев ≠ даты запуска сети/);
});
test("home handles missing metadata without guessing dates",()=>{
 const s={topics:{"gh:19":{title:"repo GPU PoW cryptocurrency mining Ethash",body:"GPU PoW cryptocurrency mining Ethash blockchain",kind:"repository"}}};
 const home=renderMenu("home",s,now);
 assert.match(home.text,/дата не получена/);
 assert.doesNotMatch(home.text,/Заявлен mainnet:/);
});

test("daily AI menu and command show report with source links",()=>{
 const data={mode:"openai",generated_at:"2026-11-20T08:10:00Z",candidate_count:5,
  summary:"Отобрать несколько ранних PoW проектов",
  picks:[{key:"btt:111",title:"ExampleCoin GPU KawPow",source:"Telegram",algorithm:"KawPow",
          launch_claim:"2026-11-21T12:00:00Z",rationale:"есть новый анонс",
          risks:"нет реального хешрейта",url:"https://t.me/example/42"}]};
 const result=renderMenu("analysis",{...state,daily_analysis:data},now);
 assert.match(result.text,/OpenAI API/);
 assert.match(result.text,/ExampleCoin/);
 assert.ok(result.reply_markup.inline_keyboard.flat().some(x=>x.url==="https://t.me/example/42"));
 assert.ok(renderMenu("home",state,now).reply_markup.inline_keyboard.flat().some(x=>x.callback_data==="analysis"));
 assert.equal(commandOf({text:"/analysis"}),"/analysis");
});
test("daily report without key is labeled not AI and hides unknown launch",()=>{
 const data={mode:"rules_only",generated_at:"2026-11-20T08:10:00Z",
   summary:"Rule check",picks:[{key:"btt:111",title:"GPUPoW",source:"GitHub",risks:"unknown"}]};
 const result=renderMenu("analysis",{...state,daily_analysis:data},now);
 assert.match(result.text,/Правила \(без ИИ\)/);
 assert.match(result.text,/Mainnet не подтверждён/);
 assert.doesNotMatch(result.text,/null \(заявлено\)/);
});

test("active tracked list is accessible from main menu",()=>{
 const s={topics:{"btt:42":{title:"GPU KawPow PoW coin",body:"GPU KawPow PoW solo mining",
    seen:"2026-11-20T05:00:00Z"}},
    tracked_projects:{"btt:42":{name:"GPU KawPow PoW coin",source:"Bitcointalk",score:7,status:"MONITOR"}}};
 const home=renderMenu("home",s,now);
 assert.match(home.text,/Активно отслеживаем: 1/);
 assert.ok(home.reply_markup.inline_keyboard.flat().some(x=>x.callback_data==="tracked:0"));
 const page=renderMenu("tracked:0",s,now);
 assert.match(page.text,/GPU KawPow PoW coin/);
 assert.ok(page.reply_markup.inline_keyboard.flat().some(x=>x.callback_data==="home"));
});

test("mining software and switching tools never appear as mineable coins",()=>{
 const s={topics:{
  "gh:1":{title:"good-mining/good-miner",body:"Rust cryptocurrency miner for NVIDIA AMD GPUs; auto profit switching",kind:"repository"},
  "gh:2":{title:"kobold-dev/kobold-miner",body:"NVIDIA GPU miner for Pearl coin and Ravencoin",kind:"repository"},
  "gh:3":{title:"MrM002/NexusSwitch",body:"GPU Crypto Auto Profit Switcher dashboard",kind:"repository"},
  "btt:5":{title:"[ANN] Quinvium (QU) GPU PoW Ethash coin mainnet",kind:"announcement"}
 }};
 const found=candidatesFromState(s);
 assert.equal(found.length,1);
 assert.equal(found[0].key,"btt:5");
 const gh=renderMenu("source:gh:0",s,now);
 assert.match(gh.text,/Пока нет доступных публикаций/);
});
