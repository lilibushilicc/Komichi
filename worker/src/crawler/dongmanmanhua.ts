/**
 * 咚漫漫画 (dongmanmanhua.cn) 爬虫 — Worker 版
 *
 * 服务端渲染页面，HTML 解析章节列表。
 * 移植自 crawler-daemon/komichi_crawler/dongmanmanhua.py
 *
 * 注意: 搜索结果链接为 /episodeList?titleNo=<id>，访问时会 302 跳转到
 * 标准列表页（/<分类>/<slug>/list?title_no=<id>），因此直接跟随重定向即可。
 */
import { BROWSER_HEADERS, STATUS_MAP, type ChapterInfo, type CrawlResult, type SourceCrawler } from './types';

const BASE_URL = 'https://www.dongmanmanhua.cn';

/** 匹配 episodeList 链接（搜索结果格式） */
const EPISODE_LIST_RE = /\/episodeList\?titleNo=(\d+)/i;
/** 匹配 list 页面 URL */
const LIST_URL_RE = /\/[^/]+\/[^/]+\/list\?title_no=\d+/i;

/** 匹配页面标题: <title>xxx_官方在线漫画阅读-咚漫漫画</title> */
const PAGE_TITLE_RE = /<title>([^<]+)<\/title>/;
/** 匹配封面: <meta property="og:image" content="..."> */
const OG_IMAGE_RE = /<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/;
/** 章节锚点: a[data-sc-name="PC_detail-page_related-title-list-item"] + 内部 img alt */
const CHAPTER_ITEM_RE =
  /data-sc-name="PC_detail-page_related-title-list-item"[\s\S]*?<img[^>]+alt="([^"]*)"/g;
/** 章节名回退: img[width="77"][height="73"] 的 alt 属性 */
const CHAPTER_ALT_RE = /<img[^>]+width="77"[^>]+height="73"[^>]+alt="([^"]*)"/g;

export const dongmanmanhuaCrawler: SourceCrawler = {
  name: 'dongmanmanhua',
  domains: ['dongmanmanhua.cn'],

  async crawl(sourceUrl: string): Promise<CrawlResult> {
    // 兼容标准 list URL 与搜索结果 /episodeList?titleNo=<id>（后者 302 到标准页）
    if (!LIST_URL_RE.test(sourceUrl) && !EPISODE_LIST_RE.test(sourceUrl)) {
      throw new Error(
        `无法识别咚漫漫画作品链接: ${sourceUrl}\n正确的格式: https://www.dongmanmanhua.cn/<分类>/<名称>/list?title_no=<id>`,
      );
    }

    const headers = { ...BROWSER_HEADERS, Referer: BASE_URL + '/' };
    const resp = await fetch(sourceUrl, {
      headers,
      redirect: 'follow',
    });
    if (!resp.ok) {
      throw new Error(`dongmanmanhua 请求失败: ${resp.status} ${sourceUrl}`);
    }
    const html = await resp.text();

    if (html.length < 500) {
      throw new Error(`dongmanmanhua 作品页不存在: ${sourceUrl}`);
    }

    // 解析标题: <title>摩登三国_官方在线漫画阅读-咚漫漫画</title>
    const titleMatch = html.match(PAGE_TITLE_RE);
    let title = titleMatch ? titleMatch[1].trim() : '';
    title = title.replace(/_官方在线漫画阅读.*$/, '').trim();
    if (!title) {
      throw new Error(`dongmanmanhua 无法解析标题: ${sourceUrl}`);
    }

    // 解析封面（优先 og:image，http 升级为 https）
    const ogMatch = html.match(OG_IMAGE_RE);
    let cover = ogMatch ? ogMatch[1].trim() : '';
    if (cover.startsWith('http://')) {
      cover = 'https://' + cover.slice(7);
    }

    // 解析状态: 页面文本含 完结/连载 等关键字
    let status = 'ongoing';
    for (const [key, val] of Object.entries(STATUS_MAP)) {
      if (html.includes(key)) {
        status = val;
        break;
      }
    }

    // 解析章节列表（页面为降序，转为升序并顺序编号）
    const rawChapters: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = CHAPTER_ITEM_RE.exec(html)) !== null) {
      const chTitle = (m[1] || '').trim();
      if (chTitle) {
        rawChapters.push(chTitle);
      }
    }
    // 回退: 缩略图 alt
    if (rawChapters.length === 0) {
      while ((m = CHAPTER_ALT_RE.exec(html)) !== null) {
        const alt = (m[1] || '').trim();
        if (alt) {
          rawChapters.push(alt);
        }
      }
    }
    rawChapters.reverse();

    const chapters: ChapterInfo[] = rawChapters.map((t, i) => ({
      chapter_num: i + 1,
      chapter_title: t || `第${i + 1}话`,
    }));

    if (chapters.length === 0) {
      throw new Error(`dongmanmanhua 无章节列表: ${title}`);
    }

    return { title, chapters, status, cover_url: cover };
  },
};
