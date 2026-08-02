/**
 * Worker 爬虫类型定义
 *
 * 将 Python CLI 的爬虫逻辑移植到 Worker，使更新不再依赖 PC。
 * 仅移植纯 HTTP 可抓取的源（mh160mh / tencent / guazi / kuaikan / dongmanmanhua / sfacg）。
 * 需要 TLS 指纹伪装（godamh）或浏览器渲染（bilibili）的源仍需 CLI。
 */

/** 章节信息 */
export interface ChapterInfo {
  chapter_num: number;
  chapter_title: string;
}

/** 爬取结果 */
export interface CrawlResult {
  title: string;
  chapters: ChapterInfo[];
  status: string;
  /** 封面图 URL（部分源可解析，用于导入时上传 R2 并回填 cover_r2_path） */
  cover_url?: string;
}

/** 爬虫接口 */
export interface SourceCrawler {
  /** 源唯一标识 */
  name: string;
  /** 该源拥有的域名，用于 URL 自动匹配 */
  domains: string[];
  /** 抓取作品信息及章节列表 */
  crawl(sourceUrl: string): Promise<CrawlResult>;
}

/** 通用请求头 */
export const BROWSER_HEADERS: Record<string, string> = {
  'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
  Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
};

/** 状态文本映射 */
export const STATUS_MAP: Record<string, string> = {
  '连载中': 'ongoing',
  '连载': 'ongoing',
  '更新中': 'ongoing',
  '完结': 'completed',
  '已完结': 'completed',
  '完结啦': 'completed',
  '全本': 'completed',
};
