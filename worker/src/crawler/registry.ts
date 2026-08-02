/**
 * 爬虫注册表 — 管理 source name -> crawler 的映射
 *
 * 使用方式:
 *   import { getCrawler, resolveSource } from './crawler';
 *   const crawler = resolveSource(sourceUrl);  // 按 URL 域名匹配
 *   const result = await crawler.crawl(sourceUrl);
 */
import type { SourceCrawler } from './types';
import { mh160mhCrawler } from './mh160mh';
import { tencentCrawler } from './tencent';
import { guaziCrawler } from './guazi';
import { kuaikanCrawler } from './kuaikan';
import { dongmanmanhuaCrawler } from './dongmanmanhua';
import { sfacgCrawler } from './sfacg';

/** 所有已注册的爬虫 */
const CRAWLERS: SourceCrawler[] = [
  mh160mhCrawler,
  tencentCrawler,
  guaziCrawler,
  kuaikanCrawler,
  dongmanmanhuaCrawler,
  sfacgCrawler,
];

/** name -> crawler 映射 */
const BY_NAME = new Map(CRAWLERS.map((c) => [c.name, c]));

/** domain -> crawler 映射 */
const BY_DOMAIN = new Map<string, SourceCrawler>();
for (const c of CRAWLERS) {
  for (const d of c.domains) {
    BY_DOMAIN.set(d.toLowerCase(), c);
  }
}

/** 按源名称获取爬虫 */
export function getCrawler(name: string): SourceCrawler | undefined {
  return BY_NAME.get(name);
}

/** 按 source_url 域名匹配爬虫 */
export function resolveSource(sourceUrl: string): SourceCrawler | undefined {
  try {
    const host = new URL(sourceUrl).hostname.toLowerCase();
    // 精确匹配或后缀匹配
    for (const [domain, crawler] of BY_DOMAIN) {
      if (host === domain || host.endsWith('.' + domain)) {
        return crawler;
      }
    }
  } catch {
    // URL 解析失败
  }
  return undefined;
}

/** 列出所有可用的 Worker 爬虫源名称 */
export function listWorkerSources(): string[] {
  return CRAWLERS.map((c) => c.name);
}
