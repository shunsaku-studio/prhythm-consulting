#!/usr/bin/env node
/**
 * docs-site/site.meta.json を正本に、VitePress 用のページ（docs-site/.generated/）と meta を生成する。
 *
 * - skills/{name}/README.md            → /skills/{name}/            （SSOT は skills/）
 * - skills/{name}/references/*.md      → /skills/{name}/references/{file}
 * - workflows/*.md                     → /workflows/{file}/
 * - cases/{case}/**.md                 → /cases/{case}/{path}/
 * - docs-site/pages/*, CONVENTIONS.md  → site.meta.json の pages
 *
 * Markdown 内の相対リンクはリポジトリ上のパスとして解決し、ページになったものはサイト内リンクに、
 * ならなかったもの（CSV、スクリプトなど）は GitHub のファイルへのリンクに書き換える。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SKILLS_DIR = path.join(ROOT, 'skills');
const WORKFLOWS_DIR = path.join(ROOT, 'workflows');
const CASES_DIR = path.join(ROOT, 'cases');
const DOCS_SITE = path.join(ROOT, 'docs-site');
const META_PATH = path.join(DOCS_SITE, 'site.meta.json');
const OUT_DIR = path.join(DOCS_SITE, '.generated');
const RESOLVED_META_PATH = path.join(OUT_DIR, '.vitepress-meta.json');
const REPO_BASE = 'https://github.com/shunsaku-studio/prhythm-consulting/blob/main';

/** 作業の型（動詞）。はしごを下りる順 */
const VERB_ORDER = ['investigate', 'split', 'interpret', 'estimate', 'decide', 'plan', 'communicate', 'audit'];
const VERB_LABELS = {
  investigate: '調べる',
  split: '分ける',
  interpret: '読み解く',
  estimate: '見積もる',
  decide: '判断材料にする',
  plan: '計画にする',
  communicate: '伝える',
  audit: '点検する',
};
const CATEGORY_ORDER = ['business', 'finance', 'delivery'];
const CATEGORY_LABELS = { business: 'ビジネス', finance: '財務', delivery: '実行計画' };
const AUTONOMY_LABELS = { solo: '◎', review: '○', together: '△' };
const AUTONOMY_TITLES = {
  solo: 'ひとりで完結',
  review: '結果をレビューに出す前提',
  together: '上位者と一緒に決める',
};
const MATURITY_LABELS = { formal: '正式', provisional: '仮の型' };
const WORKFLOW_ORDER = ['A', 'B', 'C', 'D'];

/** README の初出順（お題A のワークフロー順）。サイドバーの並び */
const SKILL_SIDEBAR_ORDER = [
  'target-math',
  'midterm-plan-reader',
  'leadership-lens',
  'issue-tree',
  'workplan',
  'pest',
  'company-financials',
  'financial-analysis',
  'growth-decomposition',
  'competitor-benchmark',
  'five-forces',
  'three-c',
  'value-chain',
  'swot',
  'market-sizing',
  'gap-bridge',
  'option-longlist',
  'initiative-sizing',
  'option-evaluation',
  'capital-capacity',
  'kpi-tree',
  'business-case-model',
  'scenario-sensitivity',
  'kpi-roadmap',
  'storyline',
  'number-audit',
];

const readText = (filePath) => fs.readFileSync(filePath, 'utf8');
const readJson = (filePath) => JSON.parse(readText(filePath));
const toPosix = (p) => p.split(path.sep).join('/');
const rel = (abs) => toPosix(path.relative(ROOT, abs));

const writeFile = (outPath, content) => {
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, content);
};

/* ---------- frontmatter ---------- */

const parseFrontmatter = (text) => {
  if (!text.startsWith('---\n')) return {};
  const end = text.indexOf('\n---', 4);
  if (end < 0) return {};
  const fm = {};
  let listKey = null;
  for (const line of text.slice(4, end).split('\n')) {
    const item = line.match(/^\s+-\s+(.+?)\s*$/);
    if (listKey && item) {
      fm[listKey].push(item[1].replace(/^["']|["']$/g, ''));
      continue;
    }
    const kv = line.match(/^([a-zA-Z_-]+):\s*(.*)$/);
    if (!kv) continue;
    const [, key, raw] = kv;
    const value = raw.trim();
    if (value === '') {
      fm[key] = [];
      listKey = key;
    } else if (value === '>-' || value === '>' || value === '|') {
      fm[key] = '';
      listKey = null;
    } else {
      fm[key] = value.replace(/^["']|["']$/g, '');
      listKey = null;
    }
  }
  return fm;
};

const toFrontmatter = (fields) => {
  const lines = ['---'];
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null && value !== '' && !(Array.isArray(value) && !value.length)) {
      lines.push(`${key}: ${JSON.stringify(value)}`);
    }
  }
  lines.push('---', '');
  return lines.join('\n');
};

const extractTitle = (content) => content.match(/^#\s+(.+)$/m)?.[1]?.trim() ?? 'Untitled';
const stripTitle = (content) => content.replace(/^#\s+.+\n+/, '');

const extractSummary = (content) => {
  const fromSection = content.match(/##\s+概要\s*\n+([\s\S]*?)(?=\n##\s|$)/)?.[1] ?? '';
  const line = fromSection
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l && !l.startsWith('<') && !l.startsWith('>'));
  if (line) return line;
  return (
    stripTitle(content)
      .split('\n')
      .map((l) => l.trim())
      .find((l) => l && !l.startsWith('<') && !l.startsWith('#') && l !== '---') ?? ''
  );
};

/** 概要の 1 文目だけ（一覧の表用） */
const firstSentence = (text) => {
  const m = text.match(/^(.+?。)/);
  return (m ? m[1] : text).replace(/\|/g, '\\|');
};

/* ---------- ルート表とリンクの書き換え ---------- */

/** リポジトリ上のパス（posix） → サイト内リンク */
const routeMap = new Map();

const routeToLink = (route) => {
  const normalized = route.replace(/^\//, '').replace(/\/index$/, '');
  return normalized === '' ? '/' : `/${normalized}/`;
};

const register = (repoRel, link) => {
  routeMap.set(repoRel, link);
  if (repoRel.endsWith('/README.md')) routeMap.set(repoRel.replace(/\/README\.md$/, ''), link);
};

const rewriteLinks = (content, sourceAbs) => {
  const baseDir = path.dirname(sourceAbs);
  return content.replace(/(!?)\]\(([^)\s]+)(\s+"[^"]*")?\)/g, (match, bang, target, title = '') => {
    if (/^(https?:|mailto:|#|\/)/.test(target)) return match;
    const [pathPart, hash = ''] = target.split('#');
    const abs = path.resolve(baseDir, decodeURI(pathPart));
    let repoRel = rel(abs).replace(/\/$/, '');
    if (repoRel.startsWith('..')) return match;
    const anchor = hash ? `#${hash}` : '';
    if (routeMap.has(repoRel)) return `${bang}](${routeMap.get(repoRel)}${anchor}${title})`;
    if (routeMap.has(`${repoRel}/README.md`)) {
      return `${bang}](${routeMap.get(`${repoRel}/README.md`)}${anchor}${title})`;
    }
    if (bang) {
      // 画像は生成先にコピーして相対参照のまま使う
      return match;
    }
    const kind = fs.existsSync(abs) && fs.statSync(abs).isDirectory() ? 'tree' : 'blob';
    return `](${REPO_BASE.replace('/blob/', `/${kind}/`)}/${repoRel}${anchor}${title})`;
  });
};

/* ---------- スキル ---------- */

const listSkills = () =>
  fs
    .readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory() && !d.name.startsWith('.'))
    .map((d) => d.name)
    .filter((name) => fs.existsSync(path.join(SKILLS_DIR, name, 'README.md')))
    .sort();

const listReferences = (slug) => {
  const dir = path.join(SKILLS_DIR, slug, 'references');
  if (!fs.existsSync(dir)) return [];
  const order = ['intake', 'method', 'pitfalls', 'questions', 'eval-scenarios', 'eval-rubric'];
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.md'))
    .map((f) => f.replace(/\.md$/, ''))
    .sort((a, b) => {
      const ia = order.indexOf(a);
      const ib = order.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib) || a.localeCompare(b);
    });
};

const buildSkillRegistry = (slugs) =>
  Object.fromEntries(
    slugs.map((slug) => {
      const readme = readText(path.join(SKILLS_DIR, slug, 'README.md'));
      const skillMd = path.join(SKILLS_DIR, slug, 'SKILL.md');
      const fm = fs.existsSync(skillMd) ? parseFrontmatter(readText(skillMd)) : {};
      const asList = (v) => (Array.isArray(v) ? v : v ? [v] : []);
      return [
        slug,
        {
          slug,
          title: extractTitle(readme),
          summary: extractSummary(readme),
          link: `/skills/${slug}/`,
          verb: fm.verb ?? null,
          categories: asList(fm.categories),
          autonomy: fm.autonomy ?? null,
          maturity: fm.maturity ?? null,
          workflows: asList(fm.workflows).map(String),
          references: listReferences(slug),
        },
      ];
    }),
  );

const REFERENCE_LABELS = {
  intake: '始める前に聞くこと',
  method: '手順',
  pitfalls: 'よく外す点',
  questions: '先輩が聞くとよい問い',
  'eval-scenarios': '評価シナリオ',
  'eval-rubric': '評価基準',
};

const registerSkillRoutes = (registry) => {
  for (const skill of Object.values(registry)) {
    register(`skills/${skill.slug}/README.md`, skill.link);
    for (const ref of skill.references) {
      register(`skills/${skill.slug}/references/${ref}.md`, `/skills/${skill.slug}/references/${ref}`);
    }
  }
};

const syncSkill = (skill) => {
  const src = path.join(SKILLS_DIR, skill.slug, 'README.md');
  const content = readText(src);
  const refs = skill.references.length
    ? [
        '',
        '## 参照資料',
        '',
        ...skill.references.map((ref) => {
          const t = extractTitle(readText(path.join(SKILLS_DIR, skill.slug, 'references', `${ref}.md`)));
          return `- [${REFERENCE_LABELS[ref] ?? t}](/skills/${skill.slug}/references/${ref}) — ${t}`;
        }),
        `- [SKILL.md（エージェント向けの手順）](${REPO_BASE}/skills/${skill.slug}/SKILL.md)`,
        '',
      ].join('\n')
    : '';
  writeFile(
    path.join(OUT_DIR, 'skills', skill.slug, 'index.md'),
    `${toFrontmatter({
      title: skill.title,
      skill: skill.slug,
      description: skill.summary,
      verb: skill.verb,
      categories: skill.categories,
      autonomy: skill.autonomy,
      maturity: skill.maturity,
      workflows: skill.workflows,
    })}<SkillInstall />\n\n${rewriteLinks(stripTitle(content), src)}${refs}`,
  );
  for (const ref of skill.references) {
    const refSrc = path.join(SKILLS_DIR, skill.slug, 'references', `${ref}.md`);
    const refContent = readText(refSrc);
    writeFile(
      path.join(OUT_DIR, 'skills', skill.slug, 'references', `${ref}.md`),
      `${toFrontmatter({ title: `${skill.slug} — ${extractTitle(refContent)}` })}${rewriteLinks(refContent, refSrc)}\n\n---\n\n[← ${skill.title}](/skills/${skill.slug}/)\n`,
    );
  }
};

/* ---------- ワークフローと案件 ---------- */

const listMarkdown = (dir) => {
  if (!fs.existsSync(dir)) return [];
  const out = [];
  const walk = (d) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const abs = path.join(d, entry.name);
      if (entry.isDirectory()) walk(abs);
      else if (entry.name.endsWith('.md')) out.push(abs);
    }
  };
  walk(dir);
  return out.sort();
};

const collectWorkflows = () =>
  listMarkdown(WORKFLOWS_DIR)
    .sort((a, b) => (path.basename(a) === 'README.md' ? -1 : path.basename(b) === 'README.md' ? 1 : a.localeCompare(b)))
    .map((abs) => {
      const isIndex = path.basename(abs) === 'README.md';
      const slug = isIndex ? '' : path.basename(abs, '.md');
      const link = isIndex ? '/workflows/' : `/workflows/${slug}/`;
      register(rel(abs), link);
      return { abs, slug, link, title: extractTitle(readText(abs)) };
    });

const collectCases = () => {
  if (!fs.existsSync(CASES_DIR)) return [];
  return fs
    .readdirSync(CASES_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => {
      const caseDir = path.join(CASES_DIR, d.name);
      const files = listMarkdown(caseDir).map((abs) => {
        const inner = toPosix(path.relative(caseDir, abs)).replace(/\.md$/, '');
        const route = inner === 'README' ? `cases/${d.name}` : `cases/${d.name}/${inner}`;
        const link = routeToLink(route);
        register(rel(abs), link);
        return { abs, inner, route, link, title: extractTitle(readText(abs)) };
      });
      const readme = files.find((f) => f.inner === 'README');
      return { slug: d.name, title: readme?.title ?? d.name, link: `/cases/${d.name}/`, files };
    });
};

const syncPlainPage = (abs, route, extra = {}) => {
  const content = readText(abs);
  const title = extra.title ?? extractTitle(content);
  const body = extra.keepTitle ? content : stripTitle(content);
  writeFile(
    path.join(OUT_DIR, route, 'index.md'),
    `${toFrontmatter({ title, ...(extra.description ? { description: extra.description } : {}) })}${extra.keepTitle ? '' : `# ${title}\n\n`}${rewriteLinks(body, abs)}`,
  );
};

/* ---------- ホーム（スキル一覧） ---------- */

const badge = (cls, label, title) =>
  `<span class="skill-badge ${cls}"${title ? ` title="${title}"` : ''}>${label}</span>`;

const categoryBadges = (cats) =>
  cats.map((c) => badge(`skill-badge--cat skill-badge--${c}`, CATEGORY_LABELS[c] ?? c)).join(' ');

const sortBySidebarOrder = (skills) => {
  const idx = new Map(SKILL_SIDEBAR_ORDER.map((s, i) => [s, i]));
  return [...skills].sort(
    (a, b) => (idx.get(a.slug) ?? 99) - (idx.get(b.slug) ?? 99) || a.slug.localeCompare(b.slug),
  );
};

const generateHome = (meta, registry) => {
  const all = Object.values(registry);
  const sections = [];
  for (const verb of VERB_ORDER) {
    const skills = sortBySidebarOrder(all.filter((s) => s.verb === verb));
    if (!skills.length) continue;
    sections.push(`### ${VERB_LABELS[verb]}`, '');
    sections.push('| スキル | 単独度 | 概要 |');
    sections.push('|--------|:------:|------|');
    for (const s of skills) {
      const auto = s.autonomy ? `<span title="${AUTONOMY_TITLES[s.autonomy]}">${AUTONOMY_LABELS[s.autonomy]}</span>` : '—';
      const tag = s.maturity === 'provisional' ? `<br>${badge('skill-badge--provisional', '仮の型')}` : '';
      sections.push(`| [${s.slug}](${s.link})${tag} | ${auto} | ${firstSentence(s.summary)} |`);
    }
    sections.push('');
  }
  const unclassified = all.filter((s) => !VERB_ORDER.includes(s.verb));
  if (unclassified.length) {
    sections.push('### 未分類', '', '| スキル | 概要 |', '|--------|------|');
    for (const s of unclassified) sections.push(`| [${s.slug}](${s.link}) | ${firstSentence(s.summary)} |`);
    sections.push('');
  }
  const intro = meta.home?.introFile ? readText(path.join(DOCS_SITE, meta.home.introFile)) : '';
  return [
    toFrontmatter({ title: meta.home?.title, description: meta.home?.description }),
    intro,
    '',
    '## スキル一覧',
    '',
    '作業の型（動詞）ごとに並べている。単独度は ◎ ひとりで完結 / ○ 結果をレビューに出す前提 / △ 上位者と一緒に決める。「仮の型」はテンプレートとよく外す点だけを置いた最小版。どのスキルをいつ使うかは[ワークフロー](/workflows/)にある。',
    '',
    ...sections,
  ].join('\n');
};

/* ---------- サイドバー ---------- */

const buildVerbSidebar = (registry) =>
  VERB_ORDER.flatMap((verb) => {
    const skills = sortBySidebarOrder(Object.values(registry).filter((s) => s.verb === verb));
    if (!skills.length) return [];
    return [
      {
        text: `スキル：${VERB_LABELS[verb]}`,
        collapsed: false,
        items: skills.map((s) => ({ text: s.slug, link: s.link })),
      },
    ];
  });

const resolveSidebarItems = (items, ctx) =>
  (items ?? []).flatMap((item) => {
    if (item.groupSkillsBy === 'verb') return buildVerbSidebar(ctx.skills);
    if (item.workflows) {
      return [{ text: item.text, collapsed: item.collapsed, items: ctx.workflows.map((w) => ({ text: w.title, link: w.link })) }];
    }
    if (item.cases) {
      return ctx.cases.map((c) => ({
        text: item.text ?? c.title,
        collapsed: item.collapsed ?? true,
        items: c.files.map((f) => ({ text: f.inner === 'README' ? '案件の進め方' : f.title, link: f.link })),
      }));
    }
    if (item.items) {
      return [{ text: item.text, ...(item.collapsed !== undefined ? { collapsed: item.collapsed } : {}), items: resolveSidebarItems(item.items, ctx) }];
    }
    if (item.link) return [{ text: item.text ?? item.link, link: item.link }];
    if (item.page) {
      const page = ctx.pages[item.page];
      if (!page) throw new Error(`sidebar: 未知の page "${item.page}"`);
      return [{ text: item.text ?? page.title, link: page.link }];
    }
    throw new Error(`sidebar item を解決できません: ${JSON.stringify(item)}`);
  });

/* ---------- main ---------- */

const main = () => {
  if (!fs.existsSync(META_PATH)) throw new Error(`site.meta.json が見つかりません: ${META_PATH}`);
  const meta = readJson(META_PATH);

  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });

  // 1. ルート表を先に作る（相互リンクの解決に使う）
  const slugs = listSkills();
  const registry = buildSkillRegistry(slugs);
  registerSkillRoutes(registry);
  const workflows = collectWorkflows();
  const cases = collectCases();
  const pages = {};
  for (const [id, cfg] of Object.entries(meta.pages ?? {})) {
    const src = path.join(cfg.source.startsWith('/') ? ROOT : DOCS_SITE, cfg.source.replace(/^\//, ''));
    if (!fs.existsSync(src)) throw new Error(`pages.${id}.source が見つかりません: ${cfg.source}`);
    const link = routeToLink(cfg.route);
    register(rel(src), link);
    pages[id] = { id, src, cfg, link, title: cfg.title ?? extractTitle(readText(src)) };
  }

  // 2. ページを書き出す
  for (const skill of Object.values(registry)) syncSkill(skill);
  for (const w of workflows) syncPlainPage(w.abs, w.slug ? `workflows/${w.slug}` : 'workflows');
  for (const c of cases) for (const f of c.files) syncPlainPage(f.abs, f.route);
  for (const p of Object.values(pages)) {
    syncPlainPage(p.src, p.cfg.route, { title: p.title, keepTitle: p.cfg.keepTitle, description: p.cfg.description });
  }
  writeFile(path.join(OUT_DIR, 'index.md'), generateHome(meta, registry));

  const resolved = {
    nav: meta.nav ?? [],
    sidebar: resolveSidebarItems(meta.sidebar ?? [], { pages, skills: registry, workflows, cases }),
    taxonomy: {
      verbs: VERB_LABELS,
      categories: CATEGORY_LABELS,
      autonomy: AUTONOMY_LABELS,
      autonomyTitles: AUTONOMY_TITLES,
      maturity: MATURITY_LABELS,
    },
  };
  writeFile(RESOLVED_META_PATH, `${JSON.stringify(resolved, null, 2)}\n`);

  const caseFiles = cases.reduce((n, c) => n + c.files.length, 0);
  console.log(
    `sync-docs: ${slugs.length} skills, ${workflows.length} workflows, ${caseFiles} case pages, ${Object.keys(pages).length} pages → ${rel(OUT_DIR)}/`,
  );
};

main();
