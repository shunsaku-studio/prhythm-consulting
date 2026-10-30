import { defineConfig } from 'vitepress';
import { withMermaid } from 'vitepress-plugin-mermaid';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const resolvedMetaPath = join(__dirname, '../.generated/.vitepress-meta.json');

type SidebarItem = { text: string; link?: string; collapsed?: boolean; items?: SidebarItem[] };

const loadResolvedMeta = (): { nav: { text: string; link: string }[]; sidebar: SidebarItem[] } => {
  if (!existsSync(resolvedMetaPath)) {
    console.warn('sync-docs が未実行です。npm run sync を先に実行してください。');
    return {
      nav: [
        { text: 'ホーム', link: '/' },
        { text: 'GitHub', link: 'https://github.com/shunsaku-studio/prhythm-consulting' },
      ],
      sidebar: [{ text: 'スキル一覧', link: '/' }],
    };
  }
  return JSON.parse(readFileSync(resolvedMetaPath, 'utf8'));
};

const meta = loadResolvedMeta();

export default withMermaid(
  defineConfig({
    title: 'Prhythm for Consulting',
    description: '抽象的な依頼を、説明できるビジネスケースへ — Agent Skills 集',
    lang: 'ja-JP',
    base: process.env.VITEPRESS_BASE ?? '/prhythm-consulting/',
    srcDir: '.generated',
    cleanUrls: true,
    lastUpdated: true,

    themeConfig: {
      nav: meta.nav,
      sidebar: meta.sidebar,
      socialLinks: [{ icon: 'github', link: 'https://github.com/shunsaku-studio/prhythm-consulting' }],
      search: { provider: 'local' },
      outline: { level: [2, 3], label: 'このページの内容' },
      docFooter: { prev: '前のページ', next: '次のページ' },
    },

    mermaid: {},
  }),
);
