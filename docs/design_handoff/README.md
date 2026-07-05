# Handoff: Reading Room — Self-Hosted RSS Reader

## Overview
**Reading Room** is a self-hosted RSS/Atom feed reader. Its defining feature is **full self-containment**: the server fetches the *complete* article for every item — following link-outs when a feed only ships a summary — and stores the body text and images locally, so the reader never bounces the user to another site. It also pulls in images, photo feeds, and comic strips inline.

The signature UX is a **layout switch** in the header that flips the entire reading experience between three radically different paradigms over the same data:

- **Home** — a warm, cozy "paper" magazine grid for relaxed leisure reading.
- **Office** — a Microsoft Outlook-style mail client (command bar + folder rail + message list + reading pane) for fast skimming at work.
- **Board** — an Atlassian Jira-style kanban that triages reading into **To Read / Reading / Read** columns.

Supporting screens: a **full-story reading view** and an **add/remove feed manager**.

---

## About the Design Files
The files in this bundle are **design references created in HTML** — a working prototype showing the intended look and behavior. **They are not production code to copy directly.**

`RSS Reader.dc.html` is a "Design Component" — an authoring format with a custom template runtime (`support.js`). **Do not ship these files or the runtime.** Open it in a browser to study look, behavior, and exact values; the file is laid out in **canvas mode** with four frames positioned side by side (main app, full-story view, feed manager). The main-app frame is fully interactive — switch layouts, toggle light/dark, mark items read, click board cards to advance them.

Your task is to **recreate these designs in a real, deployable codebase** using its established patterns and libraries. No target codebase exists yet, so **choose an appropriate stack** (see "Suggested Architecture" below) and build a git-ready deployment. The user explicitly asked for **a deployment they can push to git**.

## Fidelity
**High-fidelity (hifi).** Colors, typography, spacing, and interactions are final and intended to be matched precisely. Exact hex values, fonts, and sizes are documented below and are present inline in the HTML. Recreate the UI pixel-closely, then wire it to a real backend.

---

## Suggested Architecture
This is a guide, not a mandate — use your judgment, but the design assumes a self-hosted, single-binary-ish deployment that runs at home or in a homelab.

**Recommended stack:**
- **Backend:** A single service (Go, Python/FastAPI, or Node/Express) that:
  - Stores feeds + articles + read-state in **SQLite** (ideal for self-hosting; one file, no DB server).
  - Polls feeds on a schedule (RSS 2.0, Atom, JSON Feed).
  - **Full-text extraction:** when a feed entry has only a summary/teaser, fetch the linked page server-side and run a readability extraction (e.g. `go-readability`, `mercury-parser`, `trafilatura`, or `readability-lxml`) to store the complete article body + images locally. Rewrite/proxy image URLs so nothing hotlinks out. This is the product's core promise — prioritize it.
  - Exposes a small JSON API (see "API surface" below).
- **Frontend:** SPA (React or Vue) or server-rendered templates — the three layouts are pure CSS/markup over the same article list, so a component-based frontend with a `layout` switch maps cleanly.
- **Deployment:** Ship a **Dockerfile** + **docker-compose.yml** (the design references `localhost:8080`, `reader.home.lan`, and "docker" in its chrome). A single container mounting a volume for the SQLite DB + fetched images is the target. Include a README with `docker compose up`.

**Suggested API surface (minimum):**
- `GET /api/articles?feed=<id|all>` → list (id, feedId, feed, title, snippet, body[], type, time, words, read, status)
- `GET /api/feeds` → list (id, name, color, unread)
- `POST /api/feeds` `{url, fullText:bool}` → fetch & add (validate/discover feed from any site URL)
- `DELETE /api/feeds/:id`
- `PATCH /api/articles/:id` `{read?, status?}` → read-state / board column
- `POST /api/feeds/:id/refresh`, `POST /api/refresh` → trigger poll
- `GET /api/opml` / `POST /api/opml` → export / import

---

## Design System / Tokens

### Fonts (Google Fonts)
- **Newsreader** (serif) — app wordmark, Home card titles, full-story headlines. Weights 400/500/600.
- **Spectral** (serif) — Home body/snippets, full-story alt. 400/500/600 + italic.
- **Hanken Grotesk** (sans) — all UI chrome, Office text, Board cards. 400/500/600/700.
- **IBM Plex Mono** (mono) — metadata, timestamps, feed URLs, badges, word counts. 400/500.

### Home / "Cozy Paper" palette
Light mode (CSS custom properties used in the prototype):
- `--paper` page bg `#f7f2e8`
- `--card` surface `#fffdf8`
- `--card2` inset surface `#fbf6ec`
- `--ink` primary text `#2c2722`
- `--muted` secondary text `#8b8275`
- `--line` borders `#e8e1d2`
- `--soft` hover/segment bg `#f2ecdf`
- `--accent` terracotta `#b5532e` (user-tweakable: sage `#5f7a55`, indigo `#4f5b9a`)

Dark mode:
- `--paper` `#1b1814`, `--card` `#241f1a`, `--card2` `#2c261f`, `--ink` `#ece3d4`, `--muted` `#9c917f`, `--line` `#352f28`, `--soft` `#2c2620`, accent `#db7d52` (sage `#92ab84`, indigo `#8b97d8`).

### Office / Outlook palette
Light: bg `#faf9f8`, pane `#ffffff`, line `#edebe9`, ink `#201f1e`, sub-text `#605e5c`, selection bg `#eaf1fb`, selection bar + accent blue `#0f6cbd`, hover `#f3f2f1`. Favorites star `#e3a000`. Full-text badge green `#107c41` on `#eff6ec`/`#cfe3c4`.
Dark: bg `#1b1a19`, pane `#252423`, line `#3b3a39`, ink `#f3f2f1`, sub `#c8c6c4`, selection `#2b3a4f`, accent `#479ef5`, hover `#323130`.

### Board / Jira palette (light only in prototype)
- Column bg `#f7f8f9`, board bg `#ffffff`, borders `#dfe1e6`/`#c1c7d0`
- Card `#fff`, shadow `0 1px 1px rgba(9,30,66,0.2)` → hover `0 1px 4px rgba(9,30,66,0.3)`
- Title text `#172b4d`, meta text `#626f86`, key mono `#626f86`
- Count pill `#dce0e6` bg / `#44546f` text, radius `10px`
- Accent blue `#0c66e4`, group square `#8270db`, done-check green `#22a06b`
- Avatar `#dce0e6` bg / `#44546f` text
- Priority bars (≡ glyph): high `#e2483d`, med `#e09f3e`, low `#4a90d6` (mapped: >1000 words = high, comic = low, else med)

### Feed accent dots (per-feed identity color)
All Stories `#a89e8d` · Frontier Dispatch `#b5532e` · Paper Robots `#5f7a55` · Field Notes `#4f5b9a` · Slow Web Weekly `#9a6b3e` · Tinkerer's Almanac `#7d7468`.

### Radius / shadow
- Home cards `13px`, segments `8–11px`, buttons `9px`, badges `999px`.
- Office radius small `4–7px` (Outlook is squarer).
- Board cards `4px`, columns `6px`.
- Frame shadow (canvas): `0 2px 10px rgba(40,34,26,0.10)`.

---

## Screens / Views

### Global header (Home & shared chrome)
- Height 62px, bg `--card`, bottom border `--line`.
- Left: 27px rounded-square logo in `--accent` + **"Reading Room"** wordmark (Newsreader 22px/600).
- Center: **segmented layout switch** — pill container bg `--soft`, radius 11px, 4px padding. Three segments **Home / Office / Board** (Hanken 13.5px/600). Active segment: bg `--card`, ink text, shadow `0 1px 2px rgba(0,0,0,0.16)`. Idle: transparent, muted text.
- Right: **theme toggle** (sun ☀ / moon ☾ + "Light"/"Dark" label, bordered pill) and a primary **"+ Add feed"** button (accent bg, white text).

### 1. Home — Cozy Paper magazine
- **Layout:** left sidebar (236px) + scrolling main.
- **Sidebar:** "FEEDS" label (11px, uppercase, letter-spacing 0.14em, muted) + "+"; feed rows = colored dot + name + unread count (mono). Active row bg `--soft`. Footer: mono caption "self-hosted · localhost:8080 / last sync 4 min ago".
- **Main header:** filter name (Newsreader 26px/600) + sub "{N} stories · full text fetched on your server, no link-outs", plus a "Mark all read" outline button.
- **Grid:** `repeat(auto-fill, minmax(262px, 1fr))`, gap 18px. Card = `--card` bg, `--line` border, radius 13px, column flex.
  - **Comic** items: a 4-panel strip up top (equal flex panels, diagonal hatch placeholder, 2px gaps).
  - **Photo** items: 178px hatch placeholder labeled "[ image — drop photo ]".
  - Body: feed dot + feed name (11.5px/600 muted) + time (mono, right); title (Newsreader 17px/1.24, weight 600 unread / 480 read); snippet (Spectral 13.5px/1.55 muted); footer = meta (mono uppercase: "820 words" / "4 panels" / "photo") + a "Mark read"/"✓ Read" text button in accent.
  - Read cards: opacity 0.58, lighter title weight.

### 2. Office — Outlook mail client
- **Command bar** (46px, white): "✉ New mail" (blue icon, bold) · divider · Delete · Archive · divider · Reply · Reply all · Forward · divider · Flag · Read/Unread. Hover `--o-hover`.
- **Folder rail** (208px, white, right border): "★ Favorites" header (gold star), then feed rows = 📁 folder glyph + name + unread count. Active row: bg `--o-sel`, **3px left bar** in `--o-selbar` blue, weight 600.
- **Message list** (366px, white, right border):
  - Title row: folder name (Hanken 16px/700) + gold star + view icons (⊞ ⇅ ☰).
  - Filter row: **Focused** (blue, 600) / **Other** (muted) + "By date ⇅" right; bottom border.
  - Rows: blue unread dot (8px, transparent when read) + sender=feed name (13px, **700 unread / 400 read**) + time (right) + subject=title (12.5px, 600/ink unread, 400/sub read) + 1-line snippet (muted, ellipsis). Selected row: bg `--o-sel`, 3px blue left bar.
- **Reading pane** (fills rest, bg `--o-bg`):
  - White header block: title (Hanken 20px/600), avatar (initial) + feed name + Reply/Reply all/Forward links (blue, right) + "To: You · {time} ago".
  - Body: green **"✓ FULL STORY ON SERVER · {meta}"** badge (radius 4px, `#eff6ec`/`#cfe3c4`/`#107c41`), then comic strip / photo placeholder (cool-grey hatch `#eef0f3`/`#e2e5ea`) if applicable, then paragraphs (Hanken 14.5px/1.66).
- Folder rail + message list selection, full dark-mode variant.

### 3. Board — Jira kanban
- **Toolbar** (54px): search box ("⌕ Search board"), a round blue "B" avatar, "☰ Filter" button, right-aligned "Group: Feed" (blue outline), "⋯".
- **Group header:** ▾ caret + 18px purple `#8270db` square + filter name (Hanken 14px/600) + "({N} work items)".
- **Three columns** (equal flex, bg `#f7f8f9`, radius 6px): **TO READ / READING / READ** (11px uppercase, letter-spacing 0.06em, muted) each with a count pill; READ header has a green ✓.
  - **Cards** (white, radius 4px, Jira shadow): title (Hanken 13px/1.36, `#172b4d`); footer row = checkbox (15px; outlined `#8993a4` for open, filled green `#22a06b` ✓ in Read) + **RSS-key** (mono, e.g. `RSS-2`) + priority ≡ glyph (colored) + assignee avatar (initial).
  - To Read column has a "+ Create" affordance.
  - Read cards: opacity 0.78.

### 4. Full-story view (standalone reading page)
- Top bar (52px): "‹ All Stories" back, right actions "☆ Save", "▢ Office", primary "✓ Mark read".
- Centered column (max-width 660px): feed dot + name + "· {time} ago"; **green pill badge** "✓ FULL STORY FETCHED ON YOUR SERVER · NO LINK-OUT · 1,180 WORDS · ~5 MIN" (`#eef2e9`/`#d8e0cd`/`#5f7a55`); headline (Newsreader 38px/1.14/600, letter-spacing -0.015em); byline (Hanken 13.5px muted); body paragraphs (Newsreader 19px/1.72, `#39342c`); a 300px inline image placeholder with caption "A reading table at first light. Photo pulled inline — no hotlink."; footer nav "‹ Previous · 4 of 9 · Next story ›".

### 5. Feed manager
- Title "Manage feeds" (Newsreader 27px/600) + explainer about following link-outs to store full articles.
- **Add row:** URL input styled as `https://` prefix + path, with a primary "Fetch & add" button.
- **Full-text toggle:** green switch ON `#5f7a55` + label "Always fetch the full article — follow link-outs and store the complete text + images locally."
- **Feed list** ("5 feeds"): each row = color dot + name (14.5px/600) + URL (mono 11px muted) + a **capability pill** (green "Full-text ✓" / "Comics ✓" / "Images ✓", or grey "Summary only" `#f2ecdf`/`#e3d9c8`/muted) + "{N} new" (mono) + a 30px square **×** remove button (accent ×).
- Footer: "Import OPML" / "Export OPML" links (accent).

---

## Interactions & Behavior
- **Layout switch:** Home / Office / Board change the entire main area over the same article set. Warm feed sidebar shows in **Home only**; Office uses its own folder rail, Board its own columns.
- **Theme toggle:** light ↔ dark; both Cozy Paper and Outlook palettes have full dark variants. (Board is light-only in the prototype — pick a dark treatment if you support it.)
- **Feed filter:** clicking a feed (sidebar / folder rail) filters the list to that feed; "All Stories" shows everything. Unread counts per feed.
- **Mark read:** per-item "Mark read"/"✓ Read" toggle (Home cards, full-story); "Mark all read" affects the currently-filtered set. Read items dim and de-emphasize their title weight.
- **Office reading pane:** clicking a message selects it (blue selection bar) and renders its full body inline; first/selected message shown by default.
- **Board click-to-advance:** clicking a card cycles its status **To Read → Reading → Read → To Read**. Reaching "Read" marks the article read; leaving "Read" marks it unread (status and read-state are linked). Consider adding real drag-and-drop between columns in production.
- **Add feed:** accepts any site URL or direct feed URL; server discovers the feed and back-fills full text when "full-text" is on. Remove via ×. OPML import/export.
- **Hover states:** rows/buttons lighten to each palette's hover token; board cards raise shadow.

## State Management
- `layout`: `'home' | 'office' | 'board'` (default home; tweakable default).
- `theme`: `'light' | 'dark'`.
- `filter`: feed id or `'all'`.
- `reads`: map of articleId → bool (override of server read flag).
- `selected`: articleId for the Office reading pane (defaults to first in filtered list).
- `status`: map of articleId → `'todo' | 'doing' | 'done'` (board column; `done`⇄read are kept in sync).
- `accent`: terracotta | sage | indigo (Home accent, user tweak).
- Article shape: `{ id, feedId, feed, feedColor, type:'text'|'comic'|'photo', panels?, title, snippet, body:[string], time, words, read }`.

## Assets
- **No bundled binary assets.** All imagery in the prototype is CSS diagonal-hatch placeholders labeled for where real fetched images/comics go. In production these become the server-fetched, locally-stored images (rewritten/proxied so nothing hotlinks).
- **Fonts:** Newsreader, Spectral, Hanken Grotesk, IBM Plex Mono (Google Fonts).
- **Icons:** the prototype uses unicode glyphs (✉ 📁 ★ ✓ ≡ ⌕ etc.). Substitute your codebase's icon set (Fluent UI icons suit the Office view; Atlaskit-style icons suit the Board).

## Files
- `RSS Reader.dc.html` — the full interactive prototype (all three layouts + full-story + feed manager), canvas mode. Open in a browser to inspect.
- `support.js` — the prototype's template runtime. **Reference/runtime only — do not ship.** Inline styles and the logic class inside the HTML hold all exact values and behavior.
