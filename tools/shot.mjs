// Reading Room — offline UI screenshot harness (no deploy needed).
//
// Drives headless Edge over CDP from Node (Node 24+ has a global WebSocket, so
// no puppeteer). Serves the SPA from a local http server and preloads a data
// snapshot via window.__RR_DATA__, then captures each view to PNG.
//
// Why an http server (not data:/file://): headless Edge blocks inline scripts on
// data: URLs, so the SPA never boots.
//
// Usage:
//   node tools/shot.mjs [path/to/index.html] [outDir]
// Defaults: app/static/index.html  ->  ./  (cwd)
//
// Hooks the SPA exposes for harnessing: window.__RR_DATA__ = {feeds, articles}
// and ?layout=home|office|board. Force a view at runtime via Runtime.evaluate,
// e.g. "S.storyId=1; S.view='story'; render()" or "S.boardFilter=true; render()".

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const here = path.dirname(fileURLToPath(import.meta.url));
const HTML_PATH = process.argv[2] || path.join(here, "..", "app", "static", "index.html");
const OUTDIR = process.argv[3] || process.cwd();
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const SRV_PORT = 9000 + Math.floor(Math.random() * 900);   // randomised so back-to-back runs don't collide
const DBG_PORT = 9900 + Math.floor(Math.random() * 90);

const HTML = fs.readFileSync(HTML_PATH, "utf8");

const feeds = [
  { id: 1, name: "The Verge", color: "#e2483d", unread: 3, url: "theverge.com/rss", capability: "fulltext" },
  { id: 2, name: "Hacker News", color: "#e09f3e", unread: 2, url: "news.ycombinator.com/rss", capability: "summary" },
  { id: 3, name: "xkcd", color: "#4a90d6", unread: 1, url: "xkcd.com/rss.xml", capability: "comics" },
];
const mk = (id, feedId, title, status, words, read) => {
  const f = feeds.find(x => x.id === feedId);
  return { id, feedId, feed: f.name, feedColor: f.color, title,
    snippet: "A short preview of the article body text shown in the card and list views.",
    time: Math.floor(Date.now() / 1000) - id * 4000, read, type: "article", words, status,
    body: ["First paragraph of the fetched full article body, stored locally on the server with no link-out.",
           "Second paragraph continues the story with a little more detail and context for the reader."],
    images: [] };
};
const articles = [
  mk(1, 1, "Apple unveils its next-generation silicon roadmap", "todo", 1400, false),
  mk(2, 2, "Ask HN: what self-hosted tools changed your workflow?", "todo", 600, false),
  mk(3, 1, "The quiet rise of local-first software", "doing", 900, false),
  mk(4, 3, "Comic: standards proliferation, revisited", "todo", 0, false),
  mk(5, 2, "A deep dive into SQLite write-ahead logging", "done", 2100, true),
  mk(6, 1, "Hands-on with the newest e-ink readers", "doing", 1100, false),
];

const inject = `<script>localStorage.setItem('rr-theme','light');localStorage.setItem('rr-accent','terracotta');window.__RR_DATA__=${JSON.stringify({ feeds, articles })};</script>`;
const pageHtml = HTML.replace("</head>", inject + "</head>");

const server = http.createServer((req, res) => { res.writeHead(200, { "Content-Type": "text/html" }); res.end(pageHtml); });
await new Promise(r => server.listen(SRV_PORT, r));

const proc = spawn(EDGE, ["--headless=new", "--disable-gpu", "--hide-scrollbars",
  `--remote-debugging-port=${DBG_PORT}`, "--window-size=1400,900",
  `http://127.0.0.1:${SRV_PORT}/?layout=board`], { stdio: "ignore" });

async function getTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await fetch(`http://127.0.0.1:${DBG_PORT}/json`).then(r => r.json());
      const t = list.find(x => x.type === "page" && x.webSocketDebuggerUrl);
      if (t) return t;
    } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error("no CDP target");
}
const target = await getTarget();
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let _id = 0; const pending = new Map();
ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); } };
const cmd = (method, params = {}) => new Promise(res => { const id = ++_id; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });

await cmd("Page.enable");
await cmd("Runtime.enable");
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function shot(name) {
  const { data } = await cmd("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(path.join(OUTDIR, `${name}.png`), Buffer.from(data, "base64"));
  console.log("wrote", name);
}
async function evalJs(expr) { await cmd("Runtime.evaluate", { expression: expr }); await sleep(250); }

await sleep(1500);                                   // initial board view render
await shot("1-board");

await evalJs("S.boardFilter=true; render()");        // open the feed picker dropdown
await shot("2-board-filter-open");

await evalJs("S.filter='1'; S.boardFilter=false; render()");  // pick The Verge
await shot("3-board-filtered-verge");

await evalJs("S.filter='all'; S.storyId=1; S.view='story'; render()");  // floating story window
await shot("4-story-modal");

ws.close(); server.close(); proc.kill();
console.log("done");
process.exit(0);
