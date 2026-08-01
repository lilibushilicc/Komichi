/**
 * Komichi Worker 入口
 * 路由注册与全局中间件
 *
 * Cron scheduled handler: 每 6 小时自动爬取源站检查所有作品更新，
 * 无需 PC 运行 CLI。
 */
import { Hono } from 'hono';
import type { AppEnv, WorkRow } from './types';
import { corsMiddleware } from './middleware/cors';
import { successResponse, errorResponse } from './utils/response';
import { resolveSource } from './crawler';
import auth from './routes/auth';
import work from './routes/work';
import bookmark from './routes/bookmark';
import r2 from './routes/r2';

const app = new Hono<AppEnv>();

// 全局 CORS（私有化部署，允许所有来源）
app.use('*', corsMiddleware);

// 健康检查
app.get('/ping', (c) =>
  successResponse(c, {
    ping: 'pong',
    service: 'komichi-worker',
    time: new Date().toISOString(),
  }),
);

// 业务路由
app.route('/api/auth', auth);
app.route('/api/work', work);
app.route('/api/bookmark', bookmark);
app.route('/api/r2', r2);

// 根路径信息
app.get('/', (c) =>
  successResponse(c, {
    service: 'komichi-worker',
    version: '2.0.0',
    docs: '/ping',
  }),
);

// 404 兜底
app.notFound((c) => errorResponse(c, '接口不存在', 404, 404));

// 全局错误处理
app.onError((err, c) => {
  console.error('Unhandled error:', err);
  return errorResponse(c, '服务器内部错误', 500, 500, {
    message: err.message,
  });
});

/**
 * Cron scheduled handler
 * 定时爬取所有作品的源站，发现新章节则写入 D1。
 * 由 wrangler.toml [triggers] crons 配置驱动。
 */
async function refreshAllWorks(env: AppEnv['Bindings']): Promise<void> {
  const worksRes = await env.DB.prepare(
    'SELECT id, title, source, source_url FROM works WHERE source_url IS NOT NULL AND source_url != ""',
  ).all<WorkRow>();

  for (const w of worksRes.results) {
    const crawler = resolveSource(w.source_url || '');
    if (!crawler) continue;

    try {
      const crawlResult = await crawler.crawl(w.source_url!);

      // 查出已有章节
      const existingCh = await env.DB.prepare(
        'SELECT chapter_num FROM chapters WHERE work_id = ?',
      ).bind(w.id).all<{ chapter_num: number }>();
      const existingSet = new Set(existingCh.results.map((r) => r.chapter_num));

      const newChapters = crawlResult.chapters.filter((ch) => !existingSet.has(ch.chapter_num));

      if (newChapters.length > 0) {
        const inserts = newChapters.map((ch) =>
          env.DB.prepare(
            'INSERT INTO chapters (work_id, chapter_num, chapter_title) VALUES (?, ?, ?)',
          ).bind(w.id, ch.chapter_num, ch.chapter_title),
        );
        for (let i = 0; i < inserts.length; i += 100) {
          await env.DB.batch(inserts.slice(i, i + 100));
        }

        const maxNum = Math.max(
          ...(existingSet.size > 0 ? existingSet : [0]),
          ...newChapters.map((ch) => ch.chapter_num),
        );
        await env.DB.prepare('UPDATE works SET latest_chapter_num = ? WHERE id = ?')
          .bind(maxNum, w.id)
          .run();
      }
    } catch (e) {
      console.error(`[cron] refresh failed: ${w.title} (${w.id}):`, e);
    }
  }
}

export default {
  fetch: app.fetch,
  async scheduled(
    _event: ScheduledEvent,
    env: AppEnv['Bindings'],
    ctx: ExecutionContext,
  ): Promise<void> {
    ctx.waitUntil(refreshAllWorks(env));
  },
};
