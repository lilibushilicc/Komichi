/**
 * 瓜子漫画 (guazimanhua.com) 爬虫 — Worker 版
 *
 * 页面内嵌 schema.org JSON-LD 结构化数据，直接解析。
 * 移植自 cli/komichi_cli/crawler/guazi.py
 */
import { BROWSER_HEADERS, type ChapterInfo, type CrawlResult, type SourceCrawler } from './types';

const BASE_URL = 'https://www.guazimanhua.com';

/** 匹配 <script type="application/ld+json">...</script> */
const JSONLD_RE = /<script[^>]+type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/g;

export const guaziCrawler: SourceCrawler = {
  name: 'guazi',
  domains: ['guazimanhua.com'],

  async crawl(sourceUrl: string): Promise<CrawlResult> {
    const headers = { ...BROWSER_HEADERS, Referer: BASE_URL + '/' };
    const resp = await fetch(sourceUrl, {
      headers,
      redirect: 'follow',
    });
    if (!resp.ok) {
      throw new Error(`guazi 请求失败: ${resp.status} ${sourceUrl}`);
    }
    const html = await resp.text();

    // 提取所有 JSON-LD
    const graph: Record<string, unknown>[] = [];
    let m: RegExpExecArray | null;
    while ((m = JSONLD_RE.exec(html)) !== null) {
      try {
        const data = JSON.parse(m[1]);
        if (Array.isArray(data)) {
          graph.push(...data.filter((d) => d && typeof d === 'object'));
        } else if (data && typeof data === 'object') {
          const obj = data as Record<string, unknown>;
          if (Array.isArray(obj['@graph'])) {
            graph.push(...(obj['@graph'] as Record<string, unknown>[]).filter((d) => d && typeof d === 'object'));
          } else {
            graph.push(obj);
          }
        }
      } catch {
        // 跳过解析失败的 JSON-LD
      }
    }

    if (graph.length === 0) {
      throw new Error(`guazi 无法解析 JSON-LD: ${sourceUrl}`);
    }

    // 找 ComicStory 和 ItemList
    const comic = graph.find((g) => g['@type'] === 'ComicStory') as Record<string, unknown> | undefined;
    const chapterList = graph.find((g) => g['@type'] === 'ItemList') as Record<string, unknown> | undefined;

    if (!comic || typeof comic['name'] !== 'string') {
      throw new Error(`guazi 无法解析作品信息: ${sourceUrl}`);
    }

    const title = (comic['name'] as string).trim();

    // 解析封面图（JSON-LD image 字段）
    let cover = typeof comic['image'] === 'string' ? (comic['image'] as string).trim() : '';
    if (cover && !/^https?:\/\//i.test(cover)) {
      cover = BASE_URL + cover;
    }

    // 解析章节
    const chapters: ChapterInfo[] = [];
    if (chapterList && Array.isArray(chapterList['itemListElement'])) {
      for (const item of chapterList['itemListElement'] as Record<string, unknown>[]) {
        const name = typeof item['name'] === 'string' ? item['name'].trim() : '';
        chapters.push({
          chapter_num: chapters.length + 1,
          chapter_title: name || `第${chapters.length + 1}话`,
        });
      }
    }

    if (chapters.length === 0) {
      throw new Error(`guazi 无章节列表: ${title}`);
    }

    return { title, chapters, status: 'ongoing', cover_url: cover };
  },
};
