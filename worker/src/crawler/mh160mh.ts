/**
 * 漫画160 (mh160mh.com) 爬虫 — Worker 版
 *
 * 静态详情页，HTML 解析章节列表。
 * 移植自 cli/komichi_cli/crawler/mh160mh.py
 */
import { BROWSER_HEADERS, STATUS_MAP, type ChapterInfo, type CrawlResult, type SourceCrawler } from './types';

const BASE_URL = 'https://www.mh160mh.com';

/** 匹配章节链接 /kanmanhua/xxx/123.html */
const CHAPTER_RE = /\/kanmanhua\/[^/]+\/(\d+)\.html/;

/** 匹配 <a ... href=".../kanmanhua/xxx/123.html" ...><p>章节标题</p></a> */
const CHAPTER_ITEM_RE =
  /<a[^>]+href="([^"]*\/kanmanhua\/[^/]+\/\d+\.html)"[^>]*>(?:\s*<p[^>]*>([^<]*)<\/p>)?/g;

/** 匹配标题 */
const TITLE_RE = /<h4[^>]*>\s*<a[^>]*>([^<]+)<\/a>/;

/** 匹配状态 */
const STATUS_RE = /works-info-tc[^>]*>\s*<em[^>]*>([^<]+)<\/em>/;

export const mh160mhCrawler: SourceCrawler = {
  name: 'mh160mh',
  domains: ['mh160mh.com'],

  async crawl(sourceUrl: string): Promise<CrawlResult> {
    const headers = { ...BROWSER_HEADERS, Referer: BASE_URL + '/' };
    const resp = await fetch(sourceUrl, {
      headers,
      redirect: 'follow',
    });
    if (!resp.ok) {
      throw new Error(`mh160mh 请求失败: ${resp.status} ${sourceUrl}`);
    }
    const html = await resp.text();

    if (html.length < 500 || html.includes('无法找到该资源')) {
      throw new Error(`mh160mh 作品页不存在: ${sourceUrl}`);
    }

    // 解析标题
    const titleMatch = html.match(TITLE_RE);
    const title = titleMatch ? titleMatch[1].trim() : '';
    if (!title) {
      throw new Error(`mh160mh 无法解析标题: ${sourceUrl}`);
    }

    // 解析状态
    const statusMatch = html.match(STATUS_RE);
    const statusText = statusMatch ? statusMatch[1].trim() : '';
    const status = STATUS_MAP[statusText] || 'ongoing';

    // 解析章节列表
    // 页面为降序，转为升序并顺序编号
    const rawChapters: { href: string; title: string }[] = [];
    let m: RegExpExecArray | null;
    while ((m = CHAPTER_ITEM_RE.exec(html)) !== null) {
      const href = m[1];
      const chapterTitle = (m[2] || '').trim();
      if (CHAPTER_RE.test(href)) {
        rawChapters.push({ href, title: chapterTitle });
      }
    }
    // 反转为升序
    rawChapters.reverse();

    const chapters: ChapterInfo[] = rawChapters.map((c, i) => ({
      chapter_num: i + 1,
      chapter_title: c.title || `第${i + 1}话`,
    }));

    if (chapters.length === 0) {
      throw new Error(`mh160mh 无章节列表: ${title}`);
    }

    return { title, chapters, status };
  },
};
