/**
 * SF漫画 (sfacg.com) 爬虫 — Worker 版
 *
 * 移动端服务端渲染页面，HTML 解析章节列表。
 * 移植自 crawler-daemon/komichi_crawler/sfacg.py
 */
import { BROWSER_HEADERS, STATUS_MAP, type ChapterInfo, type CrawlResult, type SourceCrawler } from './types';

const BASE_URL = 'https://mm.sfacg.com';

/** 匹配 /b/<comicFolder>/ 或 /mh/<comicFolder>/ */
const FOLDER_RE = /\/(?:b|mh)\/([A-Za-z0-9]+)\/?/i;

/** 匹配标题: <span class="book_newtitle">元尊</span> */
const TITLE_RE = /<span[^>]*class="[^"]*book_newtitle[^"]*"[^>]*>([^<]+)<\/span>/;
/** 匹配封面: .book_info li img */
const COVER_RE = /class="[^"]*book_info[^"]*"[^>]*>[\s\S]*?<li[^>]*>[\s\S]*?<img[^>]+src="([^"]+)"/;
/** 匹配信息区: .book_info2 内前两个 span（分类 / 状态） */
const INFO2_RE = /class="[^"]*book_info2[^"]*"[^>]*>([\s\S]*?)<\/li>/;
const INFO2_SPAN_RE = /<span[^>]*>([^<]*)<\/span>/g;
/** 匹配章节区: .comic_main_list 内的 <a><div>...</div></a>（仅匹配章节/子页链接，避免页脚噪声） */
const MAIN_LIST_RE = /class="[^"]*comic_main_list[^"]*"[^>]*>([\s\S]*)$/;
const CHAPTER_ITEM_RE =
  /<a[^>]+href="\/(?:c\/\d+|b\/[A-Za-z0-9]+\/[^"]+)\/?"[^>]*>[\s\S]*?<div[^>]*>([\s\S]*?)<\/div>/g;

export const sfacgCrawler: SourceCrawler = {
  name: 'sfacg',
  domains: ['sfacg.com', 'mm.sfacg.com', 'manhua.sfacg.com'],

  async crawl(sourceUrl: string): Promise<CrawlResult> {
    const m = sourceUrl.match(FOLDER_RE);
    if (!m) {
      throw new Error(
        `无法识别 SF漫画作品链接: ${sourceUrl}\n正确的格式: https://mm.sfacg.com/b/<comicFolder>/`,
      );
    }
    const detailUrl = `${BASE_URL}/b/${m[1]}/`;

    const headers = { ...BROWSER_HEADERS, Referer: BASE_URL + '/' };
    const resp = await fetch(detailUrl, {
      headers,
      redirect: 'follow',
    });
    if (!resp.ok) {
      throw new Error(`sfacg 请求失败: ${resp.status} ${detailUrl}`);
    }
    const html = await resp.text();

    if (html.length < 500) {
      throw new Error(`sfacg 作品页不存在: ${detailUrl}`);
    }

    // 解析标题
    const titleMatch = html.match(TITLE_RE);
    const title = titleMatch ? titleMatch[1].trim() : '';
    if (!title) {
      throw new Error(`sfacg 无法解析标题: ${detailUrl}`);
    }

    // 解析封面
    const coverMatch = html.match(COVER_RE);
    let cover = coverMatch ? coverMatch[1].trim() : '';
    if (cover && !/^https?:\/\//i.test(cover)) {
      cover = 'https:' + cover;
    }

    // 解析状态: .book_info2 前两个 span（分类 / 状态）
    let status = 'ongoing';
    const info2 = html.match(INFO2_RE);
    if (info2) {
      const spans: string[] = [];
      let sm: RegExpExecArray | null;
      while ((sm = INFO2_SPAN_RE.exec(info2[1])) !== null) {
        const t = (sm[1] || '').trim();
        if (t) {
          spans.push(t);
        }
      }
      status = STATUS_MAP[spans[1] || ''] || 'ongoing';
    }

    // 解析章节列表（页面为降序，转为升序并顺序编号）
    const rawChapters: string[] = [];
    const mainList = html.match(MAIN_LIST_RE);
    if (mainList) {
      let cm: RegExpExecArray | null;
      while ((cm = CHAPTER_ITEM_RE.exec(mainList[1])) !== null) {
        const chTitle = (cm[1] || '')
          .replace(/<[^>]+>/g, '')
          .replace(/\s+/g, ' ')
          .trim();
        if (chTitle) {
          rawChapters.push(chTitle);
        }
      }
    }
    rawChapters.reverse();

    const chapters: ChapterInfo[] = rawChapters.map((t, i) => ({
      chapter_num: i + 1,
      chapter_title: t || `第${i + 1}话`,
    }));

    if (chapters.length === 0) {
      throw new Error(`sfacg 无章节列表: ${title}`);
    }

    return { title, chapters, status, cover_url: cover };
  },
};
