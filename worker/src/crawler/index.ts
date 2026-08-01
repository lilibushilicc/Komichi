/**
 * Worker 爬虫模块入口
 *
 * 导出公共接口:
 *   - resolveSource(url):  按 URL 域名匹配爬虫
 *   - getCrawler(name):    按名称获取爬虫
 *   - listWorkerSources(): 列出所有可用源
 *   - crawlSource(url):    便捷方法：自动匹配爬虫并抓取
 */
export { resolveSource, getCrawler, listWorkerSources } from './registry';
export type { ChapterInfo, CrawlResult, SourceCrawler } from './types';

import { resolveSource } from './registry';
import type { CrawlResult } from './types';

/**
 * 自动匹配爬虫并抓取源站数据
 * @throws 如果 URL 无法匹配到 Worker 爬虫（如 godamh/bilibili 需 CLI）
 */
export async function crawlSource(sourceUrl: string): Promise<CrawlResult> {
  const crawler = resolveSource(sourceUrl);
  if (!crawler) {
    throw new Error(
      `该源站不支持 Worker 爬取（可能需要 TLS 伪装或浏览器渲染），请使用 CLI: ${sourceUrl}`,
    );
  }
  return crawler.crawl(sourceUrl);
}
