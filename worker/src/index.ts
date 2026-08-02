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

// 全局 CORS：来源由环境变量 CORS_ALLOW_ORIGIN 控制（未配置则允许所有来源，见 middleware/cors.ts）
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
 * Cron 追更参数
 * - CRON_PAGE_SIZE: 每批从 D1 拉取的作品数，避免一次性 SELECT 全表占用内存/超时。
 * - CRON_CONCURRENCY: 每批内并行爬取的作品数上限，平衡速度与源站压力。
 * - CRON_LEASE_MS: 租约锁过期时间。cron 重叠触发时，已持有有效租约的运行会继续，
 *   新触发者检测到未过期租约直接跳过，避免重复写入。运行正常结束时释放租约；
 *   若进程异常退出，租约到期自动失效，不影响下次运行。
 */
const CRON_PAGE_SIZE = 200;
const CRON_CONCURRENCY = 5;
const CRON_LEASE_KEY = 'cron_refresh_lease';
const CRON_LEASE_MS = 10 * 60 * 1000; // 10 分钟

/**
 * 爬取单个作品并写入新增章节。
 * 章节去重基于 work_id + chapter_num（数据库联合唯一索引兜底），
 * 已存在的章节不会重复插入。
 */
async function refreshOneWork(
  w: WorkRow,
  env: AppEnv['Bindings'],
): Promise<void> {
  const crawler = resolveSource(w.source_url || '');
  if (!crawler) return;

  try {
    const crawlResult = await crawler.crawl(w.source_url!);

    // 查出已有章节
    const existingCh = await env.DB.prepare(
      'SELECT chapter_num FROM chapters WHERE work_id = ?',
    ).bind(w.id).all<{ chapter_num: number }>();
    const existingSet = new Set(existingCh.results.map((r) => r.chapter_num));

    const newChapters = crawlResult.chapters.filter(
      (ch) => !existingSet.has(ch.chapter_num),
    );

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

/**
 * Cron scheduled handler
 * 分页 + 并发预算 + 租约锁，定时爬取所有作品的源站检查更新。
 * 由 wrangler.toml [triggers] crons 配置驱动。
 */
async function refreshAllWorks(env: AppEnv['Bindings']): Promise<void> {
  // 1) 租约锁：若已有运行且未过期，跳过本次以免重叠写入
  const leaseRow = await env.DB.prepare(
    'SELECT value FROM settings WHERE key = ?',
  ).bind(CRON_LEASE_KEY).first<{ value: string }>();

  const now = Date.now();
  if (leaseRow?.value) {
    const expires = Number(leaseRow.value);
    if (!Number.isNaN(expires) && now < expires) {
      console.log('[cron] another refresh run is active, skip');
      return;
    }
  }

  // 2) 获取租约（写入过期时间戳；并发写入以最后一次为准）
  const leaseExpires = now + CRON_LEASE_MS;
  await env.DB.prepare(
    `INSERT INTO settings (key, value) VALUES (?, ?)
     ON CONFLICT(key) DO UPDATE SET value = excluded.value`,
  ).bind(CRON_LEASE_KEY, String(leaseExpires)).run();

  try {
    // 3) 分页遍历全部作品
    let offset = 0;
    while (true) {
      const page = await env.DB.prepare(
        `SELECT id, title, source, source_url FROM works
         WHERE source_url IS NOT NULL AND source_url != ""
         LIMIT ? OFFSET ?`,
      ).bind(CRON_PAGE_SIZE, offset).all<WorkRow>();

      if (page.results.length === 0) break;

      // 每页内按并发预算分批爬取（refreshOneWork 已自捕获异常，Promise.all 不会 reject）
      for (let i = 0; i < page.results.length; i += CRON_CONCURRENCY) {
        const slice = page.results.slice(i, i + CRON_CONCURRENCY);
        await Promise.all(slice.map((w) => refreshOneWork(w, env)));
      }

      if (page.results.length < CRON_PAGE_SIZE) break;
      offset += CRON_PAGE_SIZE;
    }
    console.log('[cron] refresh completed');
  } finally {
    // 4) 释放租约
    await env.DB.prepare(
      `INSERT INTO settings (key, value) VALUES (?, '0')
       ON CONFLICT(key) DO UPDATE SET value = '0'`,
    ).bind(CRON_LEASE_KEY).run();
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
