#!/usr/bin/env node
/**
 * ds.mjs — DeepSeek Search / Fetch 命令行 + MCP stdio 双模入口
 *
 * CLI:
 *   node ds.mjs check
 *   node ds.mjs search "<query>" [--count 10] [--min-rerank 1.5] [--min-authority 3]
 *                                 [--content] [--content-chars 600] [--ori "<原始问题>"]
 *                                 [--json]
 *   node ds.mjs fetch <url> [--max-chars 20000] [--raw] [--json]
 *   node ds.mjs --mcp          # MCP stdio 服务（供 MCP 客户端接入，非必需）
 *
 * 凭证解析（先命中先用）：
 *   1) env DEEPSEEK_API_KEY（可选 DEEPSEEK_BASE_URL）
 *   2) ~/.cc-switch/cc-switch.db —— providers 表里已管理的 DeepSeek 供应商
 *   3) ~/.workbuddy/models.json —— WorkBuddy「自定义模型」里已配置的 DeepSeek 条目
 *   4) ~/.workbuddy/secrets/deepseek_api_key
 */

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import { execFileSync } from "node:child_process";

const CC_SWITCH_DB = path.join(os.homedir(), ".cc-switch", "cc-switch.db");
const MODELS_FILE = path.join(os.homedir(), ".workbuddy", "models.json");
const KEY_FILE = path.join(os.homedir(), ".workbuddy", "secrets", "deepseek_api_key");
const DEFAULT_BASE = "https://api.deepseek.com";
const PROTOCOL_VERSION = "2024-11-05";
const SERVER_INFO = { name: "deepseek-search", version: "1.0.0" };

/* ------------------------------------------------------------------ auth */

/** 剥掉已知的路径后缀，还原成可直接拼 /v1/tools/* 的 base。 */
function normalizeBase(raw) {
  try {
    const u = new URL(raw);
    let p = u.pathname.replace(/\/+$/, "");
    let prev;
    do {
      prev = p;
      p = p.replace(/\/(v1|v1beta|anthropic|messages|chat\/completions|completions)$/i, "");
    } while (p !== prev);
    return (u.origin + p).replace(/\/+$/, "");
  } catch {
    return DEFAULT_BASE;
  }
}

function collectStrings(value, out = []) {
  if (typeof value === "string") {
    out.push(value);
    // 有些供应商把配置再嵌套一层 JSON 字符串
    if (/^\s*[{[]/.test(value)) {
      try {
        collectStrings(JSON.parse(value), out);
      } catch {
        /* not json */
      }
    }
  } else if (Array.isArray(value)) {
    for (const v of value) collectStrings(v, out);
  } else if (value && typeof value === "object") {
    for (const v of Object.values(value)) collectStrings(v, out);
  }
  return out;
}

/**
 * 从 cc-switch 的 providers 表读 DeepSeek 供应商。
 * 判定：配置里出现 api.deepseek.com，或供应商名/app_type 含 deepseek；
 * 取该供应商下第一个形如 sk-xxx 的字符串作为 key。
 */
function fromCcSwitch() {
  if (!fs.existsSync(CC_SWITCH_DB)) return null;

  let rows;
  try {
    const raw = execFileSync(
      "/usr/bin/sqlite3",
      ["-json", "-readonly", CC_SWITCH_DB, "select app_type, name, settings_config from providers"],
      { encoding: "utf8", timeout: 5000, stdio: ["ignore", "pipe", "ignore"] }
    );
    rows = JSON.parse(raw || "[]");
  } catch {
    return null;
  }
  if (!Array.isArray(rows)) return null;

  for (const row of rows) {
    const strings = collectStrings(String(row.settings_config || ""));
    const named = /deepseek/i.test(`${row.name || ""} ${row.app_type || ""}`);
    const pointsToDs = strings.some((s) => /api\.deepseek\.com/i.test(s));
    if (!named && !pointsToDs) continue;

    const key = strings.find((s) => /^sk-[A-Za-z0-9_-]{16,}$/.test(s.trim()));
    if (!key) continue;

    const baseUrl = strings.find((s) => /^https?:\/\//i.test(s.trim()) && /deepseek/i.test(s));
    return {
      key: key.trim(),
      base: baseUrl ? normalizeBase(baseUrl.trim()) : DEFAULT_BASE,
      source: `cc-switch#${row.name || row.app_type}`,
    };
  }
  return null;
}

function fromWorkBuddyModels() {
  let entries;
  try {
    entries = JSON.parse(fs.readFileSync(MODELS_FILE, "utf8"));
  } catch {
    return null;
  }
  if (!Array.isArray(entries)) return null;

  const hit =
    entries.find((m) => typeof m?.url === "string" && /api\.deepseek\.com/i.test(m.url) && m?.apiKey) ||
    entries.find((m) => /deepseek/i.test(String(m?.vendor || "")) && m?.apiKey);
  if (!hit) return null;

  let base = DEFAULT_BASE;
  try {
    const u = new URL(hit.url);
    base = (u.origin + u.pathname.replace(/\/chat\/completions\/?$/, "")).replace(/\/+$/, "");
  } catch {
    /* keep default */
  }
  return { key: String(hit.apiKey).trim(), base, source: `models.json#${hit.name || hit.id || hit.vendor}` };
}

let cachedAuth = null;

function resolveAuth() {
  if (cachedAuth) return cachedAuth;

  const envKey = (process.env.DEEPSEEK_API_KEY || "").trim();
  if (envKey) {
    cachedAuth = {
      key: envKey,
      base: (process.env.DEEPSEEK_BASE_URL || DEFAULT_BASE).replace(/\/+$/, ""),
      source: "env DEEPSEEK_API_KEY",
    };
    return cachedAuth;
  }

  const fromSw = fromCcSwitch();
  if (fromSw) {
    if (process.env.DEEPSEEK_BASE_URL) fromSw.base = process.env.DEEPSEEK_BASE_URL.replace(/\/+$/, "");
    cachedAuth = fromSw;
    return cachedAuth;
  }

  const fromModels = fromWorkBuddyModels();
  if (fromModels) {
    if (process.env.DEEPSEEK_BASE_URL) fromModels.base = process.env.DEEPSEEK_BASE_URL.replace(/\/+$/, "");
    cachedAuth = fromModels;
    return cachedAuth;
  }

  try {
    const fileKey = fs.readFileSync(KEY_FILE, "utf8").trim();
    if (fileKey) {
      cachedAuth = {
        key: fileKey,
        base: (process.env.DEEPSEEK_BASE_URL || DEFAULT_BASE).replace(/\/+$/, ""),
        source: "secrets/deepseek_api_key",
      };
      return cachedAuth;
    }
  } catch {
    /* ignore */
  }

  throw new Error(
    "缺少 DeepSeek API Key。按优先级任选其一：\n" +
      "  1) 在 cc-switch 里配置一个 DeepSeek 供应商（会读取 ~/.cc-switch/cc-switch.db）\n" +
      `  2) 在 WorkBuddy「自定义模型」配置指向 api.deepseek.com 的 DeepSeek 模型（会读取 ${MODELS_FILE}）\n` +
      "  3) export DEEPSEEK_API_KEY=sk-xxx\n" +
      `  4) printf 'sk-xxx' > ${KEY_FILE} && chmod 600 ${KEY_FILE}`
  );
}

/* ------------------------------------------------------------------ http */

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function post(pathname, body, { timeoutMs = 60000, retries = 2 } = {}) {
  const { key, base } = resolveAuth();
  let lastErr;

  for (let attempt = 0; attempt <= retries; attempt++) {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), timeoutMs);
    try {
      const res = await fetch(base + pathname, {
        method: "POST",
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ac.signal,
      });
      const raw = await res.text();
      let json;
      try {
        json = raw ? JSON.parse(raw) : {};
      } catch {
        json = { raw };
      }
      if (!res.ok) {
        const msg = json?.error?.message || raw.slice(0, 300) || res.statusText;
        const err = new Error(`HTTP ${res.status} ${msg}`);
        err.status = res.status;
        if ((res.status === 408 || res.status === 429 || res.status >= 500) && attempt < retries) {
          lastErr = err;
          await sleep(500 * 2 ** attempt);
          continue;
        }
        throw err;
      }
      return json;
    } catch (e) {
      if (e.name === "AbortError") {
        lastErr = new Error(`请求超时（${timeoutMs}ms）`);
        if (attempt < retries) {
          await sleep(500 * 2 ** attempt);
          continue;
        }
        throw lastErr;
      }
      throw e;
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastErr;
}

/* ------------------------------------------------------------------ format */

/** DeepSeek Fetch 会转义正文标点（https\:\/\/…），代码块外还原，保证 URL 可直接复用。 */
function unescapeMarkdown(md) {
  return md
    .split(/(```[\s\S]*?```)/g)
    .map((part, i) => (i % 2 === 1 ? part : part.replace(/\\([\\`*_{}\[\]()#+\-.!|>~:/.])/g, "$1")))
    .join("");
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString().slice(0, 10);
}

function renderResults(query, results, { minRerank = 0, minAuthority = -1, contentChars = 0, total = null } = {}) {
  const kept = results.filter(
    (r) => r.rerank_score >= minRerank && (r.authority == null || r.authority === -1 || r.authority >= minAuthority)
  );
  if (!kept.length) {
    return `query: ${query}\n未命中结果（原始 ${results.length} 条，过滤后 0 条）。`;
  }

  const lines = [
    `query: ${query}`,
    `返回 ${total ?? results.length} 条，展示 ${kept.length} 条` +
      (minRerank > 0 ? `（rerank_score ≥ ${minRerank}）` : "") +
      (minAuthority > 0 ? `（authority ≥ ${minAuthority}）` : ""),
    "",
  ];

  kept.forEach((r, i) => {
    const meta = [
      r.site_name || null,
      fmtDate(r.date) || null,
      `相关 ${typeof r.rerank_score === "number" ? r.rerank_score.toFixed(2) : "?"}`,
      r.authority >= 0 ? `权威 ${r.authority}` : null,
    ]
      .filter(Boolean)
      .join(" · ");

    lines.push(`${i + 1}. [${r.title || "(无标题)"}](${r.url})`);
    if (meta) lines.push(`   ${meta}`);
    if (r.summary) lines.push(`   ${r.summary.replace(/\s+/g, " ").trim()}`);
    else if (r.snippet) lines.push(`   ${r.snippet.replace(/\s+/g, " ").trim()}`);
    if (contentChars > 0 && r.content) {
      const body = r.content.replace(/\s+/g, " ").trim();
      lines.push(`   正文摘录：${body.slice(0, contentChars)}${body.length > contentChars ? "…" : ""}`);
    }
    lines.push("");
  });

  return lines.join("\n").trim();
}

/* ------------------------------------------------------------------ tools */

async function doSearch(opts) {
  const body = {
    query: opts.query,
    count: opts.count ?? 10,
    need_content: Boolean(opts.content),
  };
  if (opts.ori) body.ori_question = opts.ori;
  if (opts.localization) body.localization = opts.localization;

  const data = await post("/v1/tools/search", body, { timeoutMs: 30000 });
  const results = Array.isArray(data.results) ? data.results : [];
  if (opts.json) return JSON.stringify(results, null, 2);
  return renderResults(opts.query, results, {
    minRerank: opts.minRerank ?? 0,
    minAuthority: opts.minAuthority ?? -1,
    contentChars: opts.contentChars ?? 0,
  });
}

async function doFetch(opts) {
  const data = await post("/v1/tools/fetch", { url: opts.url }, { timeoutMs: 60000 });
  if (opts.json) return JSON.stringify(data, null, 2);

  const max = opts.maxChars ?? 20000;
  let content = typeof data.content === "string" ? data.content : "";
  if (!opts.raw) content = unescapeMarkdown(content);
  const truncated = content.length > max;

  return [
    `title: ${data.title || "(无标题)"}`,
    `url: ${opts.url}`,
    `length: ${content.length} chars${truncated ? ` (已截断至 ${max})` : ""}`,
    "",
    truncated ? content.slice(0, max) + "\n…(truncated)" : content,
  ].join("\n");
}

/* ------------------------------------------------------------------ mcp */

const MCP_TOOLS = [
  {
    name: "ds_search",
    description:
      "使用 DeepSeek 自研搜索引擎检索实时网页，返回带 rerank_score(0~3，≥1.5 优质) 与 authority(0~4，≥3 极权威) 的结构化结果。" +
      'query 支持操作符：site: / -site: / -关键词 / "精确短语" / lang:zh,en / after:2025-01-01 / before:2026-01-01。' +
      "需要读全文时改用 ds_fetch。",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "搜索词，1~128 字符，支持操作符" },
        count: { type: "integer", minimum: 1, maximum: 50, default: 10 },
        ori_question: { type: "string", description: "触发搜索的用户原始问题，可提升意图理解" },
        need_content: { type: "boolean", default: false },
        min_rerank: { type: "number", default: 0 },
        min_authority: { type: "integer", default: -1 },
        content_chars: { type: "integer", default: 0 },
      },
      required: ["query"],
    },
  },
  {
    name: "ds_fetch",
    description: "按 URL 抓取单个网页，返回干净的 Markdown 正文（含标题）。受站点访问策略影响，可能 404。",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "http/https URL，≤8192 字符" },
        max_chars: { type: "integer", default: 20000 },
      },
      required: ["url"],
    },
  },
];

async function runMcpTool(name, a = {}) {
  if (name === "ds_search") {
    return doSearch({
      query: a.query,
      count: a.count ?? 10,
      content: a.need_content,
      ori: a.ori_question,
      minRerank: a.min_rerank ?? 0,
      minAuthority: a.min_authority ?? -1,
      contentChars: a.content_chars ?? 0,
    });
  }
  if (name === "ds_fetch") return doFetch({ url: a.url, maxChars: a.max_chars ?? 20000 });
  throw new Error(`未知工具：${name}`);
}

function startMcp() {
  const send = (msg) => process.stdout.write(JSON.stringify(msg) + "\n");
  const reply = (id, result) => send({ jsonrpc: "2.0", id, result });
  const replyErr = (id, code, message) => send({ jsonrpc: "2.0", id, error: { code, message } });

  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", async (line) => {
    const s = line.trim();
    if (!s) return;
    let msg;
    try {
      msg = JSON.parse(s);
    } catch {
      return;
    }
    if (msg.id == null) return;

    try {
      switch (msg.method) {
        case "initialize":
          reply(msg.id, { protocolVersion: PROTOCOL_VERSION, capabilities: { tools: {} }, serverInfo: SERVER_INFO });
          break;
        case "ping":
          reply(msg.id, {});
          break;
        case "tools/list":
          reply(msg.id, { tools: MCP_TOOLS });
          break;
        case "tools/call":
          try {
            const text = await runMcpTool(msg.params?.name, msg.params?.arguments || {});
            reply(msg.id, { content: [{ type: "text", text }], isError: false });
          } catch (e) {
            reply(msg.id, { content: [{ type: "text", text: `错误：${e.message}` }], isError: true });
          }
          break;
        default:
          replyErr(msg.id, -32601, `Method not found: ${msg.method}`);
      }
    } catch (e) {
      replyErr(msg.id, -32603, e.message);
    }
  });
  rl.on("close", () => process.exit(0));
}

/* ------------------------------------------------------------------ cli */

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const k = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith("--")) out[k] = true;
      else {
        out[k] = next;
        i++;
      }
    } else out._.push(a);
  }
  return out;
}

const num = (v, d) => (v === undefined || v === true ? d : Number(v) || d);

const USAGE = `用法:
  ds.mjs check
  ds.mjs search "<query>" [--count 10] [--min-rerank 1.5] [--min-authority 3]
                          [--content] [--content-chars 600] [--ori "<原始问题>"] [--json]
  ds.mjs fetch <url> [--max-chars 20000] [--raw] [--json]
  ds.mjs --mcp            # MCP stdio 服务

示例:
  ds.mjs search "广西 医保 双通道 药店 政策 site:gov.cn after:2026-01-01" --min-rerank 1.5
  ds.mjs fetch "https://www.ithome.com/1/014/291.htm" --max-chars 3000
`;

async function main() {
  const argv = process.argv.slice(2);

  if (!argv.length || argv[0] === "--help" || argv[0] === "help") {
    process.stdout.write(USAGE);
    process.exit(argv.length ? 0 : 2);
  }

  if (argv[0] === "--mcp") {
    startMcp();
    return;
  }

  const [cmd, ...rest] = argv;
  const o = parseArgs(rest);

  if (cmd === "check") {
    const a = resolveAuth();
    console.log(`key 来源: ${a.source}`);
    console.log(`base: ${a.base}`);
    return;
  }

  if (cmd === "search") {
    const query = o._[0];
    if (!query) {
      console.error("缺少 query。\n" + USAGE);
      process.exit(2);
    }
    const out = await doSearch({
      query,
      count: num(o.count, 10),
      content: Boolean(o.content),
      ori: typeof o.ori === "string" ? o.ori : undefined,
      localization: typeof o.localization === "string" ? o.localization : undefined,
      minRerank: num(o["min-rerank"], 0),
      minAuthority: typeof o["min-authority"] === "string" ? Number(o["min-authority"]) : -1,
      contentChars: num(o["content-chars"], 0),
      json: Boolean(o.json),
    });
    console.log(out);
    return;
  }

  if (cmd === "fetch") {
    const url = o._[0];
    if (!url) {
      console.error("缺少 url。\n" + USAGE);
      process.exit(2);
    }
    const out = await doFetch({
      url,
      maxChars: num(o["max-chars"], 20000),
      raw: Boolean(o.raw),
      json: Boolean(o.json),
    });
    console.log(out);
    return;
  }

  console.error(`未知子命令: ${cmd}\n` + USAGE);
  process.exit(2);
}

main().catch((e) => {
  console.error(`错误: ${e.message}`);
  process.exit(1);
});
