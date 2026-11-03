// The constitution: what the Lab may do on its own (constitution/constitution.json, owned by the owner).
// classify() names the class of an action or a request; judge() turns a class into a verdict:
//   do      level 3, or a level earned by a clean run
//   recall  level 2: it happens after the recall window unless someone pulls it
//   ask     level 1 (with a default and a time) or level 0 (no default)
//   block   a "never" rule matched; nothing happens and nobody is asked
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
// The repo file is the seed. The live copy (edited on Board day) lives with the Lab log, so the rack checkout stays clean.
export const SEED_PATH = path.join(HERE, "../constitution/constitution.json");
export const STATE_PATH = path.join(process.env.HOME || "", ".local/share/ttl-autopilot/constitution.json");
export const CONSTITUTION_PATH = process.env.AUTOPILOT_CONSTITUTION || (fs.existsSync(STATE_PATH) ? STATE_PATH : SEED_PATH);
export function seedLiveCopy() {
  if (process.env.AUTOPILOT_CONSTITUTION || fs.existsSync(STATE_PATH)) return false;
  fs.mkdirSync(path.dirname(STATE_PATH), { recursive: true }); fs.copyFileSync(SEED_PATH, STATE_PATH); return true;
}
const livePath = () => process.env.AUTOPILOT_CONSTITUTION || (fs.existsSync(STATE_PATH) ? STATE_PATH : SEED_PATH);

let cached = null, cachedAt = 0;
let cachedPath = "";
export function constitution() {
  const p = livePath(), st = fs.statSync(p);
  if (!cached || st.mtimeMs !== cachedAt || p !== cachedPath) { cached = validate(JSON.parse(fs.readFileSync(p, "utf8"))); cachedAt = st.mtimeMs; cachedPath = p; }
  return cached;
}
/** Write a new constitution (Board day). Validated first; the caller records the change. */
export function writeConstitution(next) {
  validate(next); const p = livePath();
  if (p === SEED_PATH && !process.env.AUTOPILOT_CONSTITUTION) throw new Error("no live copy: seed it first");
  const tmp = `${p}.${process.pid}.tmp`; fs.writeFileSync(tmp, JSON.stringify(next, null, 2) + "\n"); fs.renameSync(tmp, p); cached = null;
}

export function validate(c) {
  const bad = [];
  for (const [id, k] of Object.entries(c.classes || {})) {
    if (![0, 1, 2, 3].includes(k.level)) bad.push(`${id}: level must be 0-3`);
    if (!c.people?.[k.owner]) bad.push(`${id}: owner ${k.owner} is not in people`);
    if (k.level === 1 && !(k.defaultAfterHours > 0 && k.default)) bad.push(`${id}: level 1 needs defaultAfterHours and default`);
    if (k.level === 2 && !(k.recallMinutes > 0)) bad.push(`${id}: level 2 needs recallMinutes`);
    if (!k.why) bad.push(`${id}: every class says why`);
  }
  for (const n of c.never || []) if (n.match) new RegExp(n.match, "i");   // throws on a broken pattern
  if (bad.length) throw new Error(`constitution: ${bad.join("; ")}`);
  return c;
}

// ---- words (the same families business.mjs uses on the console, so both agree while they run side by side)
const W = {
  refund: /\brefund\w*\b/i,
  recurring: /\b(subscri\w+|licen[cs]e fee|monthly plan|annual plan|paid plan|pro plan|per month|renew\w*|trial ends|free trial)\b|\/mo\b/i,
  upgrade: /\bupgrad(e|ing)\b/i,
  price: /\b(price change|change the price|reprice|discount code|discount|coupon|sale price)\b/i,
  money: /\$\s?\d|\b(pay|paid|payment|fees?|invoice|bill|billing|pric(e|es|ing)|cost|budget|spend|grant|bookkeep\w*|sales tax|purchase|re-?order|buy)\b/i,
  safety: /\b(cpc|cpsc|recall|chok\w*|small parts|16 cfr|astm|age grad\w*|warning label|choking|hazard|injur\w*)\b/i,
  legal: /\b(legal|lawyer|attorney|insurance|insurer|liabilit\w*|licen[cs]e\w*|trademark|copyright|contract|sign(ed|ing)? (the|a|an)|terms of service|privacy policy|regulator|filing|llc|irs|comptroller)\b/i,
  customer: /\b(order\s?#?\d+|customer|inquiry|enquiry|keychain claim|shipping|delivery|toy request|wholesale|quote request)\b/i,
  market: /\b(markets?|booth|stall|festival|fair|eventeny|vendor application)\b/i,
  press: /\b(press|journalist|reporter|podcast|interview|partnership|sponsor\w*|collab\w*|giveaway|ad campaign|advert\w*)\b/i,
  launch: /\b(go on sale|put on sale|list (it|the toy) for sale|new listing|launch (the|a) (toy|product))\b/i,
  printer: /\b(printers?|plates?|filament|nozzle|ams|firmware|slic(e|er|ing)|3mf|g-?code|print farm|spools?|purge|bambu)\b/i,
  crew: /\b(kr|okr|q\d-o\d|json|schema|repo|commit|deploy script|console|tmux|pane|cron|timer|script|harness|rhythm|standup|ceo tick)\b/i,
  physical: /\b(hand-?write|pick up|pack|photograph|drive|load (the )?filament|plug in|carry|label|ship it|post office|clean|vacuum|wipe|oil|tighten)\b/i,
};
// "upgrade Slack to Pro" costs money every month; a firmware upgrade does not
const isRecurring = (t) => W.recurring.test(t) || (W.upgrade.test(t) && !/\bfirmware\b/i.test(t));
const BULK_FROM = /^(hello|hi|info|news|newsletter|no-?reply|donotreply|do-not-reply|marketing|admin|team|updates?|notifications?|offers?|promo)@|@(e?mail|mailer|news|marketing|send|bounce)\./i;
const STANDING = { "social-queue": "social.post", "inbox-routine": "customer.reply.known", "market-comms": "market.comms", "sms-ack": "customer.text.ack", "sms-routine": "customer.text.reply", "youtube-mirror": "social.mirror", "x-engagement": "social.engage", "ig-engagement": "social.engage" };

const AMOUNT = /\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)/;
export const amountIn = (t) => { const m = String(t || "").match(AMOUNT); return m ? Number(m[1].replace(/,/g, "")) : 0; };

// a decision-shaped request (an agent's ask, a CEO proposal): the title says what it is about; the body is read only when the title is silent
function decisionClass(title, all, cost) {
  for (const t of [title, all]) {
    if (W.safety.test(t)) return { class: "safety.decision", why: "mentions child safety" };
    if (W.legal.test(t)) return { class: "legal.decision", why: "legal or licence words" };
    if (W.refund.test(t)) return { class: "money.refund", why: "a refund" };
    if (isRecurring(t)) return { class: "money.recurring", why: "a recurring cost" };
    if (W.price.test(t)) return { class: "money.price", why: "a price or discount" };
    if (W.money.test(t) || cost > 0) return { class: "money.spend", why: "spends money" };
    if (W.launch.test(t)) return { class: "product.launch", why: "a toy going on sale" };
    if (W.press.test(t)) return { class: "press.partner", why: "press or partnership" };
    if (W.customer.test(t)) return { class: "business.decision", area: "customers", why: "about a customer or an order" };
    if (W.crew.test(t)) return { class: "crew.internal", why: "about the crew's own tools" };
    if (W.printer.test(t)) return { class: "farm.plan", why: "about printers or prints" };
    if (W.market.test(t)) return { class: "business.decision", area: "markets", why: "about a market" };
  }
  return { class: "business.decision", why: "a business call" };
}

/**
 * Name the class of an action or request.
 * @param {{ actor?: string, kind?: string, standing?: string, title?: string, body?: string, category?: string, fromEmail?: string, cost?: number, askKind?: string, class?: string, tags?: string[] }} a
 * @returns {{ class: string, area?: string, why: string }}
 */
export function classify(a) {
  const c = constitution();
  if (a.class && c.classes[a.class]) return { class: a.class, why: "named by the caller" };
  const title = String(a.title || ""), all = `${title} ${String(a.body || "").slice(0, 2400)}`;
  const kind = String(a.kind || "").toLowerCase(), actor = String(a.actor || "").toLowerCase();
  const cost = Number(a.cost) || 0;
  if (a.standing && STANDING[a.standing]) return { class: STANDING[a.standing], why: `standing class ${a.standing}` };
  // safety and legal outrank everything else: "TONIGHT: sell no more Minis" was filed as physical, but it is a safety call (J-160)
  if (W.safety.test(title) || (!a.kind && W.safety.test(all))) return { class: "safety.decision", why: "mentions child safety" };
  if (a.askKind === "physical") return { class: "hands.task", why: "needs hands" };
  switch (kind) {
    case "blog": case "lab-notes": return { class: "blog.post", why: "a Lab Notes post" };
    case "press": case "partnership": case "ad": return { class: "press.partner", why: kind };
    case "newsletter": case "list-email": return { class: "email.list", why: "an email to a list" };
    case "social": case "reel": case "post": return { class: W.press.test(title) ? "press.partner" : "social.new", why: "a post outside an approved series" };
    case "sms": case "text": return { class: "customer.text.reply", why: "a reply on the Lab line" };
    case "email": case "reply": {
      const cat = String(a.category || "");
      if (BULK_FROM.test(String(a.fromEmail || "")) && !["customer", "order"].includes(cat)) return { class: "drop.marketing", why: `bulk sender ${a.fromEmail}` };
      if (cat === "legal" || W.legal.test(title)) return { class: "legal.decision", why: "a legal email" };
      if (W.press.test(title)) return { class: "press.partner", why: "press or partnership email" };
      if (cat === "market" || (W.market.test(title) && !W.customer.test(title))) return { class: "market.email", why: "a market organiser email" };
      if (cat === "marketing" || cat === "newsletter" || cat === "platform") return { class: "drop.marketing", why: `category ${cat}` };
      return { class: "customer.reply.new", why: "a customer email" };
    }
    case "purchase": case "order-supplies": return money(c, cost, all);
    case "deploy": return { class: W.crew.test(title) ? "crew.internal" : "site.deploy", why: "a site deploy" };
    case "feature": return { class: "site.feature", why: "a new site feature" };
    case "print": case "schedule": return { class: "farm.plan", why: "print scheduling" };
    case "chore": case "task": case "physical": return { class: "hands.task", why: "needs hands" };
  }
  if (a.askKind === "money") { const d = decisionClass(title, all, cost); return d.class.startsWith("money.") && d.class !== "money.spend" ? d : money(c, cost || amountIn(title), all); }
  const d = decisionClass(title, all, cost);
  if (d.class === "money.spend") return money(c, cost || amountIn(title), all);
  if (d.class === "hands.task" || (a.askKind !== "decide" && W.physical.test(title) && !W.safety.test(title))) return { class: "hands.task", why: "needs hands" };
  return d;
}

function money(c, cost, text) {
  if (W.refund.test(text)) return { class: "money.refund", why: "a refund" };
  if (isRecurring(text)) return { class: "money.recurring", why: "a recurring cost" };
  if (cost > c.money.perPurchase) return { class: "money.over-cap", why: `$${cost} is over the $${c.money.perPurchase} cap` };
  return { class: "money.spend", why: cost ? `$${cost}, inside the cap` : "spends money" };
}

/** The never rules that match, if any. */
export function neverHit(a) {
  const text = `${a.title || ""} ${String(a.body || "").slice(0, 4000)}`, tags = new Set(a.tags || []);
  for (const n of constitution().never || []) {
    if (n.tag && tags.has(n.tag)) return n;
    if (n.match && new RegExp(n.match, "i").test(text)) return n;
  }
  return null;
}

/**
 * The verdict for one action. ctx.trust: { [class]: level } earned levels; ctx.monthSpend: dollars already committed this month.
 * @returns {{ verdict: "do"|"recall"|"ask"|"block", class: string, level: number, owner: string, area: string, why: string, recallUntil?: string, default?: { action: string, at: string } | null, rule?: string }}
 */
export function judge(a, ctx = {}) {
  const c = constitution(), now = ctx.now ?? Date.now();
  const n = neverHit(a);
  const cl = classify(a);
  let klass = cl.class, why = cl.why;
  if (klass === "money.spend") {
    const cost = Number(a.cost) || amountIn(a.title);
    if ((ctx.monthSpend || 0) + cost > c.money.perMonth) { klass = "money.over-cap"; why = `would take the month to $${(ctx.monthSpend || 0) + cost}, over $${c.money.perMonth}`; }
  }
  const k = c.classes[klass];
  const base = { class: klass, owner: k.owner, area: cl.area || k.area, why };
  if (n) return { ...base, verdict: "block", level: k.level, rule: n.id, why: n.text };
  // learned stops (Board day, from repeated answers): "You declined 4 replies to marketing emails. Stop drafting them?"
  const sender = String(a.fromEmail || "").split("@")[1]?.toLowerCase() || "";
  const stop = (c.stops || []).find((x) => (!x.class || x.class === klass) && (!x.agent || x.agent === a.actor) && (!x.sender || x.sender === sender) && (!x.match || new RegExp(x.match, "i").test(a.title || "")));
  if (stop) return { ...base, verdict: "block", level: k.level, rule: `stop:${stop.id}`, why: stop.text };
  const earned = !k.fixed && ctx.trust?.[klass] != null ? Math.max(k.level, ctx.trust[klass]) : k.level;
  // Board dials: an area can run one step more careful (-1) or bolder (+1); fixed classes never move, and nothing public goes past "do it with a recall"
  const offset = k.fixed ? 0 : Number(c.dials?.areas?.[base.area] || 0);
  const ceiling = ["customers", "going-out", "markets"].includes(base.area) ? 2 : 3;
  let level = Math.max(0, Math.min(Math.max(k.level, Math.min(earned + offset, ceiling)), 3));
  if (offset < 0) level = Math.max(0, earned + offset);
  // Pause the Lab: nothing leaves on its own and no default fires; the crew keeps working inside
  if (c.dials?.pause && !["crew", "hands"].includes(base.area) && !klass.startsWith("farm.")) return { ...base, verdict: "ask", level: 0, default: null, why: `${why} · the Lab is paused` };
  const iso = (ms) => new Date(ms).toISOString();
  // a draft that cites something not on the record is always a person's call (shadow run 2026-09-27)
  if ((a.tags || []).includes("unverified")) return { ...base, verdict: "ask", level: 0, default: null, why: `${why} · cites something not on the record` };
  if (level === 3) return { ...base, verdict: "do", level };
  if (level === 2) return { ...base, verdict: "recall", level, recallUntil: iso(now + (k.recallMinutes || k.earnedRecallMinutes || 60) * 60e3) };
  if (level === 1) return { ...base, verdict: "ask", level, default: { action: k.default, at: iso(now + k.defaultAfterHours * 3600e3) } };
  return { ...base, verdict: "ask", level: 0, default: null };
}
