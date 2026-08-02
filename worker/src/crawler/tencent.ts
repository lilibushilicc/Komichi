/**
 * 腾讯动漫 (ac.qq.com) 爬虫 — Worker 版
 *
 * 静态服务端渲染页面，HTML 解析章节列表。
 * 移植自 cli/komichi_cli/crawler/tencent.py
 */
import { BROWSER_HEADERS, STATUS_MAP, type ChapterInfo, type CrawlResult, type SourceCrawler } from './types';

const BASE_URL = 'https://ac.qq.com';

/** 匹配章节链接 /ComicView/index/id/xxx/cid/123 */
const CHAPTER_RE = /\/ComicView\/index\/id\/\d+\/cid\/(\d+)/;

/**
 * 匹配 chapter-page-all 区域内的章节 <a> 标签
 * 实际格式: <a target="_blank" title="章节标题" href="/ComicView/index/id/xxx/cid/123">
 */
const CHAPTER_ITEM_RE =
  /<a[^>]+target="_blank"[^>]+title="([^"]*)"[^>]+href="([^"]*\/ComicView\/index\/id\/\d+\/cid\/\d+)"[^>]*>/g;

/** 匹配 <h2 class="works-intro-title ..."><strong>标题</strong></h2> */
const TITLE_RE = /<h2[^>]*class="[^"]*works-intro-title[^"]*"[^>]*>\s*<strong>([^<]+)<\/strong>/;

/** 匹配 <label class="works-intro-status">连载中</label> */
const STATUS_RE = /<label[^>]*class="[^"]*works-intro-status[^"]*"[^>]*>\s*([^<]+)\s*<\/label>/;

/** 匹配封面图: <div class="works-cover ...">...<img src="..."> */
const COVER_RE = /class="[^"]*works-cover[^"]*"[^>]*>[\s\S]*?<img[^>]+src="([^"]+)"/;

export const tencentCrawler: SourceCrawler = {
  name: 'tencent',
  domains: ['ac.qq.com'],

  async crawl(sourceUrl: string): Promise<CrawlResult> {
    const headers = { ...BROWSER_HEADERS, Referer: BASE_URL + '/' };
    const resp = await fetch(sourceUrl, {
      headers,
      redirect: 'follow',
    });
    if (!resp.ok) {
      throw new Error(`tencent 请求失败: ${resp.status} ${sourceUrl}`);
    }
    const html = await resp.text();

    if (html.length < 500) {
      throw new Error(`tencent 作品页不存在: ${sourceUrl}`);
    }

    // 解析标题: <h2 class="works-intro-title ui-left"><strong>标题</strong></h2>
    const titleMatch = html.match(TITLE_RE);
    const title = titleMatch ? titleMatch[1].trim() : '';
    if (!title) {
      throw new Error(`tencent 无法解析标题: ${sourceUrl}`);
    }

    // 解析状态: <label class="works-intro-status">连载中</label>
    const statusMatch = html.match(STATUS_RE);
    const statusText = statusMatch ? statusMatch[1].trim() : '';
    const status = STATUS_MAP[statusText] || 'ongoing';

    // 解析封面图: <div class="works-cover ..."><img src="...">
    const coverMatch = html.match(COVER_RE);
    let cover = coverMatch ? coverMatch[1].trim() : '';
    if (cover.startsWith('//')) {
      cover = 'https:' + cover;
    } else if (cover && !/^https?:\/\//i.test(cover)) {
      cover = BASE_URL + cover;
    }

    // 解析章节列表
    // chapter-page-all <ol> 内为升序，每个 <a> 带 title 和 href
    const chapters: ChapterInfo[] = [];
    let m: RegExpExecArray | null;
    while ((m = CHAPTER_ITEM_RE.exec(html)) !== null) {
      const chapterTitle = (m[1] || '').trim();
      const href = m[2];
      if (CHAPTER_RE.test(href)) {
        chapters.push({
          chapter_num: chapters.length + 1,
          chapter_title: chapterTitle || `第${chapters.length + 1}话`,
        });
      }
    }

    if (chapters.length === 0) {
      throw new Error(`tencent 无章节列表: ${title}`);
    }

    return { title, chapters, status, cover_url: cover };
  },
};
