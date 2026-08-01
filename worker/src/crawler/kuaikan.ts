/**
 * 快看漫画 (kuaikanmanhua.com) 爬虫 — Worker 版
 *
 * PC 端为 SPA，数据走内部 JSON API：
 *   1. GET /v2/pweb/comic/inner/<comic_id> → 返回 topic_id
 *   2. GET /v2/pweb/topic/<topic_id>       → 作品信息 + 完整章节列表
 * 移植自 cli/komichi_cli/crawler/kuaikan.py
 */
import { BROWSER_HEADERS, STATUS_MAP, type ChapterInfo, type CrawlResult, type SourceCrawler } from './types';

const BASE_URL = 'https://www.kuaikanmanhua.com';
const API_URL = 'https://www.kuaikanmanhua.com/v2/pweb';

const COMIC_RE = /\/web\/comic\/(\d+)/;

export const kuaikanCrawler: SourceCrawler = {
  name: 'kuaikan',
  domains: ['kuaikanmanhua.com'],

  async crawl(sourceUrl: string): Promise<CrawlResult> {
    const m = sourceUrl.match(COMIC_RE);
    if (!m) {
      throw new Error(`kuaikan 无法识别作品链接: ${sourceUrl}`);
    }
    const comicId = m[1];

    const headers = {
      ...BROWSER_HEADERS,
      Accept: 'application/json',
      Referer: `${BASE_URL}/web/comic/`,
    };

    // 步骤1: 获取 topic_id
    const innerResp = await fetch(`${API_URL}/comic/inner/${comicId}?source=&pc_go_app_exp=`, {
      headers,
      redirect: 'follow',
    });
    if (!innerResp.ok) {
      throw new Error(`kuaikan inner 请求失败: ${innerResp.status}`);
    }
    const inner = (await innerResp.json()) as Record<string, unknown>;
    const innerData = (inner['data'] as Record<string, unknown>) || {};
    const topicInfo = (innerData['topic_info'] as Record<string, unknown>) || {};
    const topicId = topicInfo['id'];
    if (!topicId) {
      throw new Error(`kuaikan 作品不存在或已下线: ${comicId}`);
    }

    // 步骤2: 获取作品详情 + 章节列表
    const detailResp = await fetch(`${API_URL}/topic/${topicId}?source=&pc_go_app_exp=`, {
      headers,
      redirect: 'follow',
    });
    if (!detailResp.ok) {
      throw new Error(`kuaikan topic 请求失败: ${detailResp.status}`);
    }
    const detail = (await detailResp.json()) as Record<string, unknown>;
    const detailData = (detail['data'] as Record<string, unknown>) || {};
    const info = (detailData['topic_info'] as Record<string, unknown>) || {};

    const title = typeof info['title'] === 'string' ? info['title'].trim() : '';
    if (!title) {
      throw new Error(`kuaikan 无法解析标题: ${comicId}`);
    }

    const statusText = typeof info['update_status'] === 'string' ? info['update_status'].trim() : '';
    const status = STATUS_MAP[statusText] || 'ongoing';

    // 解析章节列表（接口返回按发布时间升序）
    const chapters: ChapterInfo[] = [];
    const comics = Array.isArray(info['comics']) ? (info['comics'] as Record<string, unknown>[]) : [];
    for (const c of comics) {
      if (!c || !c['id']) continue;
      const chapterTitle = typeof c['title'] === 'string' ? c['title'].trim() : '';
      chapters.push({
        chapter_num: chapters.length + 1,
        chapter_title: chapterTitle || `第${chapters.length + 1}话`,
      });
    }

    if (chapters.length === 0) {
      throw new Error(`kuaikan 无章节列表: ${title}`);
    }

    return { title, chapters, status };
  },
};
