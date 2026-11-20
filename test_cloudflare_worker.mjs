import test from "node:test";
import assert from "node:assert/strict";
import worker,{parseAllowed,commandOf,formatReply,renderMenu,candidatesFromState} from "./cloudflare-worker.mjs";

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
test("authorized recipients",()=>assert.deepEqual([...parseAllowed(env)],["123","456"]));
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
test("source browser includes github and telegram records regardless of candidate score",()=>{
  const s={topics:{
    "gh:99":{title:"Example cryptocurrency repository",seen:"2026-11-20T04:00:00Z",
      source:"GitHub — repository",url:"https://github.com/example/coin"},
    "tg:miningrelease:301":{title:"Coin Name NewCoin Algo: KawPow",seen:"2026-11-20T05:00:00Z",
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
  assert.equal(renderMenu("source:pool:0",s,now).reply_markup.inline_keyboard[0][0].callback_data,"entry:pool:0:0");
});
