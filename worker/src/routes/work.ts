/**
 * 作品路由
 * - GET  /api/work/list            获取作品列表（分页 + status 过滤）
 * - GET  /api/work/check/:id       检查作品更新（?force=true 实时爬取源站）
 * - GET  /api/work/refresh-all     批量检查所有作品更新（Cron / 手动触发）
 * - GET  /api/work/search          搜索代理：转发到 VPS /api/search（无需鉴权）
 * - POST /api/work/import-via-vps  导入代理：转发到 VPS /api/import（需 CRAWLER 权限）
 * - GET  /api/work/vps-url         获取当前 VPS_URL 配置（需 CRAWLER 权限）
 * - PUT  /api/work/vps-url         更新 VPS_URL 配置（需 CRAWLER 权限）
 * - GET  /api/work/:id             获取作品详情（含章节列表）
 * - POST /api/work/update          新增/更新作品数据（需 CRAWLER 权限）
 * - POST /api/work/import          通过 source_url 导入（Worker 能爬则爬，否则回退 VPS）
 *
 * 注意: 静态路由 (/list, /check/:id, /refresh-all, /search, /import-via-vps, /vps-url) 必须在
 *       参数路由 (/:id) 之前注册，以避免被参数路由捕获。
 */
import { Hono } from 'hono';
import type { AppEnv, WorkRow, ChapterRow } from '../types';
import { successResponse, errorResponse } from '../utils/response';
import { authMiddleware, requireRole } from '../middleware/auth';
import { rateLimit } from '../middleware/rateLimit';
import { crawlSource, resolveSource } from '../crawler';
import type { CrawlResult } from '../crawler';
import { BROWSER_HEADERS } from '../crawler/types';
import { getVpsUrl, getSetting, setSetting } from '../utils/settings';

const work = new Hono<AppEnv>();

/** 安全解析正整数，失败返回默认值 */
function parsePositiveInt(value: string | undefined, defaultValue: number): number {
  if (!value) return defaultValue;
  const n = parseInt(value, 10);
  return Number.isFinite(n) && n > 0 ? n : defaultValue;
}

const COVER_CONTENT_TYPES: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  gif: 'image/gif',
  webp: 'image/webp',
  bmp: 'image/bmp',
  avif: 'image/avif',
};

/** 从封面 URL 提取扩展名（与 VPS daemon 的 _ext_of 一致，默认 jpg） */
function coverExt(coverUrl: string): string {
  let pathname = coverUrl;
  try {
    pathname = new URL(coverUrl).pathname;
  } catch {
    // 保留原始字符串
  }
  const m = pathname.match(/\.([a-z0-9]+)$/i);
  const ext = m ? m[1].toLowerCase() : '';
  return COVER_CONTENT_TYPES[ext] ? ext : 'jpg';
}

/**
 * 下载源站封面并上传到 R2（komichi/covers/<work_id>.<ext>）。
 * 与 VPS daemon runner.import_work 的封面流程保持一致。
 * 失败时返回 null，不影响作品元数据写入。
 */
async function uploadCoverToR2(
  env: AppEnv['Bindings'],
  workId: number,
  coverUrl: string,
): Promise<string | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const resp = await fetch(coverUrl, {
      headers: { ...BROWSER_HEADERS },
      redirect: 'follow',
      signal: controller.signal,
    });
    if (!resp.ok) {
      console.log(`[work/import] 封面下载失败 ${resp.status}: ${coverUrl}`);
      return null;
    }
    const arrayBuffer = await resp.arrayBuffer();
    const ext = coverExt(coverUrl);
    const key = `komichi/covers/${workId}.${ext}`;
    const contentType =
      resp.headers.get('content-type')?.split(';')[0]?.trim() ||
      COVER_CONTENT_TYPES[ext] ||
      'application/octet-stream';
    await env.BUCKET.put(key, arrayBuffer, { httpMetadata: { contentType } });
    return key;
  } catch (e) {
    console.log(`[work/import] 封面上传失败: ${e instanceof Error ? e.message : String(e)}`);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 转发请求到 VPS crawler-daemon 并返回其 JSON 响应。
 * 网络不可达或响应非 JSON 时抛出异常，由调用方捕获后返回 502。
 *
 * 内置 15 秒超时（AbortController），防止 fetch 挂起导致 Cloudflare 返回空 502。
 *
 * @param vpsBaseUrl 已规范化的 VPS 基地址
 * @param path       以 / 开头的路径（含 query string）
 * @param init       可选的 fetch 初始化参数（method / headers / body）
 * @param timeoutMs  超时毫秒数，默认 15000
 */
async function fetchVpsJson(
  vpsBaseUrl: string,
  path: string,
  init?: RequestInit,
  timeoutMs: number = 15000,
): Promise<unknown> {
  const url = `${vpsBaseUrl}${path}`;
  console.log(`[fetchVpsJson] fetching: ${url}`);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const resp = await fetch(url, {
      ...init,
      signal: controller.signal,
      // Cloudflare Workers 需要显式指定 redirect 行为
      redirect: 'follow',
    });
    console.log(`[fetchVpsJson] response status: ${resp.status}`);

    if (!resp.ok) {
      const errText = await resp.text().catch(() => '');
      throw new Error(`VPS returned HTTP ${resp.status}: ${resp.statusText} (body: ${errText.substring(0, 200)})`);
    }
    const text = await resp.text();
    try {
      return JSON.parse(text);
    } catch {
      throw new Error(`VPS returned non-JSON (len=${text.length}): ${text.substring(0, 200)}`);
    }
  } finally {
    clearTimeout(timer);
  }
}

/**
 * GET /api/work/list
 * Query: page (默认 1), size (默认 20), status (可选)
 */
work.get('/list', async (c) => {
  const page = parsePositiveInt(c.req.query('page'), 1);
  const size = parsePositiveInt(c.req.query('size'), 20);
  const status = c.req.query('status')?.trim() || '';
  const offset = (page - 1) * size;

  // 限制单页最大条数，防止滥用
  const limitSize = Math.min(size, 100);

  let listSql = 'SELECT * FROM works';
  let countSql = 'SELECT COUNT(*) as total FROM works';
  const params: (string | number)[] = [];

  if (status) {
    listSql += ' WHERE status = ?';
    countSql += ' WHERE status = ?';
    params.push(status);
  }

  listSql += ' ORDER BY create_time DESC LIMIT ? OFFSET ?';

  const listPromise = c.env.DB.prepare(listSql).bind(...params, limitSize, offset).all<WorkRow>();
  const countPromise = c.env.DB.prepare(countSql).bind(...params).first<{ total: number }>();

  const [listRes, countRes] = await Promise.all([listPromise, countPromise]);

  return successResponse(c, {
    list: listRes.results.map((row) => ({
      ...row,
      auto_refresh: !!resolveSource(row.source_url || ''),
    })),
    total: countRes?.total ?? 0,
    page,
    size: limitSize,
  });
});

/**
 * GET /api/work/search
 * 搜索代理：转发到 VPS crawler-daemon 的 GET /api/search，返回各源站搜索结果。
 * 需登录（USER 即可），避免匿名调用对 VPS 造成滥用/DoS。
 *
 * 注意: 此路由必须在 /:id 参数路由之前注册，否则会被 /:id 捕获。
 *
 * Query: keyword (必填)
 */
work.get('/search', rateLimit({ keyPrefix: 'search', windowSec: 60, max: 30 }), authMiddleware, async (c) => {
  const keyword = c.req.query('keyword')?.trim() || '';
  if (!keyword) {
    return errorResponse(c, 'keyword 不能为空', 400);
  }

  const vpsBaseUrl = await getVpsUrl(c.env.DB, c.env.VPS_URL);
  console.log(`[search] keyword="${keyword}", vpsBaseUrl="${vpsBaseUrl}"`);
  if (!vpsBaseUrl) {
    return errorResponse(c, 'VPS 搜索服务未配置', 503, 503, null);
  }

  try {
    const data = await fetchVpsJson(
      vpsBaseUrl,
      `/api/search?keyword=${encodeURIComponent(keyword)}`,
      undefined,
      20000, // 搜索给 20 秒超时（源站爬取较慢）
    );
    console.log('[search] success, returning data');
    return c.json(data);
  } catch (e) {
    const isAbort = e instanceof Error && e.name === 'AbortError';
    const detail = e instanceof Error ? e.message : String(e);
    console.error(`[search] failed: ${isAbort ? 'TIMEOUT' : 'ERROR'} - ${detail}`);
    return errorResponse(
      c,
      isAbort
        ? `VPS 搜索超时（20秒），VPS 可能不可达或源站响应过慢: ${vpsBaseUrl}`
        : `VPS 搜索服务不可达: ${detail}`,
      502,
      502,
      { vps_url: vpsBaseUrl, error_type: isAbort ? 'timeout' : 'fetch_error' },
    );
  }
});

/**
 * GET /api/work/check/:id
 * 检查作品更新。
 * - 默认: 仅读取 D1 本地数据（快速，返回当前缓存的最新状态）
 * - ?force=true: 实时爬取源站，发现新章节则写入 D1（慢，但保证最新）
 */
work.get('/check/:id', async (c) => {
  const id = parsePositiveInt(c.req.param('id'), 0);
  if (id <= 0) {
    return errorResponse(c, '无效的作品 ID', 400);
  }

  const workRow = await c.env.DB.prepare(
    'SELECT id, title, latest_chapter_num, status, source, source_url FROM works WHERE id = ?',
  ).bind(id).first<WorkRow>();

  if (!workRow) {
    return errorResponse(c, '作品不存在', 404, 404);
  }

  // 直接取 chapters 表的实际最大值，不再依赖可能过时的 works.latest_chapter_num
  const maxChapterRes = await c.env.DB.prepare(
    'SELECT MAX(chapter_num) as max_num FROM chapters WHERE work_id = ?',
  ).bind(id).first<{ max_num: number | null }>();
  let maxChapterNum = maxChapterRes?.max_num ?? 0;

  // 自动修复不一致
  if (maxChapterNum !== workRow.latest_chapter_num) {
    await c.env.DB.prepare('UPDATE works SET latest_chapter_num = ? WHERE id = ?')
      .bind(maxChapterNum, id)
      .run();
  }

  // ?force=true: 实时爬取源站
  const force = c.req.query('force') === 'true';
  let forceError: string | null = null;
  let newChapterCount = 0;

  if (force && workRow.source_url) {
    try {
      const result = await crawlSource(workRow.source_url);

      // 查出 D1 中已有的章节号集合
      const existingCh = await c.env.DB.prepare(
        'SELECT chapter_num FROM chapters WHERE work_id = ?',
      ).bind(id).all<{ chapter_num: number }>();
      const existingSet = new Set(existingCh.results.map((r) => r.chapter_num));

      // 找出源站有但 D1 没有的新章节
      const newChapters = result.chapters.filter((ch) => !existingSet.has(ch.chapter_num));

      if (newChapters.length > 0) {
        // 批量插入新章节
        const inserts = newChapters.map((ch) =>
          c.env.DB.prepare(
            'INSERT INTO chapters (work_id, chapter_num, chapter_title) VALUES (?, ?, ?)',
          ).bind(id, ch.chapter_num, ch.chapter_title),
        );
        for (let i = 0; i < inserts.length; i += 100) {
          await c.env.DB.batch(inserts.slice(i, i + 100));
        }

        // 更新 latest_chapter_num
        maxChapterNum = Math.max(maxChapterNum, ...newChapters.map((ch) => ch.chapter_num));
        await c.env.DB.prepare('UPDATE works SET latest_chapter_num = ? WHERE id = ?')
          .bind(maxChapterNum, id)
          .run();

        newChapterCount = newChapters.length;
      }
    } catch (e) {
      forceError = e instanceof Error ? e.message : String(e);
    }
  }

  const latestChapter = maxChapterNum > 0
    ? await c.env.DB.prepare(
        'SELECT * FROM chapters WHERE work_id = ? AND chapter_num = ?',
      ).bind(id, maxChapterNum).first<ChapterRow>()
    : null;

  // 解析爬虫源信息
  const crawler = workRow.source_url ? resolveSource(workRow.source_url) : undefined;

  return successResponse(c, {
    work: {
      id: workRow.id,
      title: workRow.title,
      latest_chapter_num: maxChapterNum,
      status: workRow.status,
      source: workRow.source || crawler?.name || 'unknown',
      source_url: workRow.source_url,
      auto_refresh: !!crawler,
    },
    latest_chapter: latestChapter ?? null,
    has_update: newChapterCount > 0,
    new_chapter_count: newChapterCount,
    force_error: forceError,
  });
});

/**
 * GET /api/work/refresh-all
 * 批量检查所有作品的源站更新。供 Cron 定时调用，也可手动触发。
 * 仅处理 source_url 能匹配到 Worker 爬虫的作品。
 */
work.get('/refresh-all', async (c) => {
  // 查出所有有 source_url 的作品
  const worksRes = await c.env.DB.prepare(
    'SELECT id, title, source, source_url, cover_r2_path FROM works WHERE source_url IS NOT NULL AND source_url != ""',
  ).all<WorkRow>();

  const results: Array<{
    id: number;
    title: string;
    source: string | null;
    new_chapters: number;
    error: string | null;
  }> = [];

  for (const w of worksRes.results) {
    const entry = {
      id: w.id,
      title: w.title,
      source: w.source,
      new_chapters: 0,
      error: null as string | null,
    };

    // 检查是否有对应的 Worker 爬虫
    const crawler = resolveSource(w.source_url || '');
    if (!crawler) {
      entry.error = `不支持的源: ${w.source_url}`;
      results.push(entry);
      continue;
    }

    try {
      const crawlResult = await crawler.crawl(w.source_url!);

      // 查出已有章节
      const existingCh = await c.env.DB.prepare(
        'SELECT chapter_num FROM chapters WHERE work_id = ?',
      ).bind(w.id).all<{ chapter_num: number }>();
      const existingSet = new Set(existingCh.results.map((r) => r.chapter_num));

      // 找出新章节
      const newChapters = crawlResult.chapters.filter((ch) => !existingSet.has(ch.chapter_num));

      if (newChapters.length > 0) {
        const inserts = newChapters.map((ch) =>
          c.env.DB.prepare(
            'INSERT INTO chapters (work_id, chapter_num, chapter_title) VALUES (?, ?, ?)',
          ).bind(w.id, ch.chapter_num, ch.chapter_title),
        );
        for (let i = 0; i < inserts.length; i += 100) {
          await c.env.DB.batch(inserts.slice(i, i + 100));
        }

        // 更新 latest_chapter_num
        const maxNum = Math.max(
          ...(existingSet.size > 0 ? existingSet : [0]),
          ...newChapters.map((ch) => ch.chapter_num),
        );
        await c.env.DB.prepare('UPDATE works SET latest_chapter_num = ? WHERE id = ?')
          .bind(maxNum, w.id)
          .run();

        entry.new_chapters = newChapters.length;
      }

      // 回填封面：作品缺少封面时下载源站封面并上传 R2
      if (!w.cover_r2_path && crawlResult.cover_url) {
        const uploaded = await uploadCoverToR2(c.env, w.id, crawlResult.cover_url);
        if (uploaded) {
          await c.env.DB.prepare('UPDATE works SET cover_r2_path = ? WHERE id = ?')
            .bind(uploaded, w.id)
            .run();
        }
      }
    } catch (e) {
      entry.error = e instanceof Error ? e.message : String(e);
    }

    results.push(entry);
  }

  const totalNew = results.reduce((sum, r) => sum + r.new_chapters, 0);
  const totalError = results.filter((r) => r.error).length;

  return successResponse(c, {
    total: results.length,
    new_chapters: totalNew,
    errors: totalError,
    details: results,
  });
});

/**
 * POST /api/work/import-via-vps  （需 CRAWLER 权限）
 * 导入代理：将 { source_url } 透传给 VPS crawler-daemon 的 POST /api/import，
 * 由 VPS 爬取后回写 Worker D1。
 *
 * Body: { "source_url": "https://..." }
 *
 * - VPS_URL 未配置 → { code:503, msg:"VPS 导入服务未配置", data:null }
 * - VPS 不可达     → { code:502, msg:"VPS 导入服务不可达", data:null }
 * - 成功           → 直接透传 VPS 返回的 JSON
 */
work.post('/import-via-vps', authMiddleware, requireRole('CRAWLER'), async (c) => {
  let body: { source_url?: string };
  try {
    body = (await c.req.json()) as { source_url?: string };
  } catch {
    return errorResponse(c, '请求体不是合法的 JSON', 400);
  }

  const sourceUrl = (body.source_url || '').trim();
  if (!sourceUrl) {
    return errorResponse(c, 'source_url 不能为空', 400);
  }

  const vpsBaseUrl = await getVpsUrl(c.env.DB, c.env.VPS_URL);
  if (!vpsBaseUrl) {
    return errorResponse(c, 'VPS 导入服务未配置', 503, 503, null);
  }

  try {
    const data = await fetchVpsJson(vpsBaseUrl, '/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_url: sourceUrl }),
    });
    return c.json(data);
  } catch {
    return errorResponse(c, 'VPS 导入服务不可达', 502, 502, null);
  }
});

/**
 * GET /api/work/vps-url （需 CRAWLER 权限）
 * 获取当前 VPS_URL 配置（D1 优先，回退 env 绑定）。
 */
work.get('/vps-url', authMiddleware, requireRole('CRAWLER'), async (c) => {
  const dbValue = await getSetting(c.env.DB, 'vps_url');
  const envValue = c.env.VPS_URL || '';
  return successResponse(c, {
    vps_url: dbValue || envValue || '',
    source: dbValue ? 'database' : envValue ? 'env' : 'unset',
  });
});

/**
 * PUT /api/work/vps-url （需 CRAWLER 权限）
 * 更新 VPS_URL 配置，写入 D1 settings 表。
 * 后续 search / import-via-vps 将使用新地址，无需重新部署 Worker。
 *
 * Body: { "vps_url": "https://xxx.trycloudflare.com" }
 */
work.put('/vps-url', authMiddleware, requireRole('CRAWLER'), async (c) => {
  let body: { vps_url?: string };
  try {
    body = (await c.req.json()) as { vps_url?: string };
  } catch {
    return errorResponse(c, '请求体不是合法的 JSON', 400);
  }

  const vpsUrl = (body.vps_url || '').trim().replace(/\/+$/, '');
  if (!vpsUrl) {
    return errorResponse(c, 'vps_url 不能为空', 400);
  }
  if (!vpsUrl.startsWith('http://') && !vpsUrl.startsWith('https://')) {
    return errorResponse(c, 'vps_url 必须以 http:// 或 https:// 开头', 400);
  }

  await setSetting(c.env.DB, 'vps_url', vpsUrl);
  return successResponse(c, { vps_url: vpsUrl }, 'VPS_URL 已更新');
});

/**
 * GET /api/work/vps-debug
 * 诊断端点：从 Worker 环境测试 VPS 连通性，返回详细的诊断信息。
 * 无需鉴权，用于排查 502 问题。
 */
work.get('/vps-debug', async (c) => {
  const vpsBaseUrl = await getVpsUrl(c.env.DB, c.env.VPS_URL);
  const diagnostics: Record<string, unknown> = {
    vps_url: vpsBaseUrl,
    vps_url_source: vpsBaseUrl ? 'configured' : 'unset',
    worker_time: new Date().toISOString(),
  };

  if (!vpsBaseUrl) {
    return successResponse(c, { ...diagnostics, error: 'VPS_URL 未配置' });
  }

  const pingUrl = `${vpsBaseUrl}/ping`;
  diagnostics.ping_url = pingUrl;

  const startTime = Date.now();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);

  try {
    const resp = await fetch(pingUrl, {
      signal: controller.signal,
      redirect: 'follow',
    });
    const elapsed = Date.now() - startTime;
    diagnostics.fetch_status = resp.status;
    diagnostics.fetch_status_text = resp.statusText;
    diagnostics.elapsed_ms = elapsed;

    const text = await resp.text();
    diagnostics.response_length = text.length;
    diagnostics.response_preview = text.substring(0, 500);

    try {
      diagnostics.response_json = JSON.parse(text);
    } catch {
      diagnostics.response_json = null;
    }

    return successResponse(c, diagnostics);
  } catch (e) {
    const elapsed = Date.now() - startTime;
    const isAbort = e instanceof Error && e.name === 'AbortError';
    diagnostics.elapsed_ms = elapsed;
    diagnostics.error_type = isAbort ? 'timeout' : (e instanceof Error ? e.name : typeof e);
    diagnostics.error_message = e instanceof Error ? e.message : String(e);
    return successResponse(c, diagnostics);
  } finally {
    clearTimeout(timer);
  }
});

/**
 * GET /api/work/:id
 * 获取作品详情，包含章节列表
 */
work.get('/:id', async (c) => {
  const id = parsePositiveInt(c.req.param('id'), 0);
  if (id <= 0) {
    return errorResponse(c, '无效的作品 ID', 400);
  }

  const workRow = await c.env.DB.prepare('SELECT * FROM works WHERE id = ?')
    .bind(id)
    .first<WorkRow>();

  if (!workRow) {
    return errorResponse(c, '作品不存在', 404, 404);
  }

  const chaptersRes = await c.env.DB.prepare(
    'SELECT id, work_id, chapter_num, chapter_title, create_time FROM chapters WHERE work_id = ? ORDER BY chapter_num ASC',
  ).bind(id).all<ChapterRow>();

  return successResponse(c, {
    ...workRow,
    auto_refresh: !!resolveSource(workRow.source_url || ''),
    chapters: chaptersRes.results,
  });
});

/**
 * POST /api/work/update  （需 CRAWLER 权限）
 * 新增或更新作品数据（不含章节图片），基于 source_url 或 title 进行 upsert。
 *
 * 兼容两种请求体格式：
 *   扁平格式: { title, category, chapters: [...] }
 *   包装格式: { work: { title, ... }, chapters: [...] }  （CLI 使用）
 *
 * Body:
 * {
 *   "title": "作品名",
 *   "category": "分类",
 *   "description": "作品简介",
 *   "cover_r2_path": "covers/xxx.jpg",
 *   "source_url": "https://来源",
 *   "status": "ongoing",
 *   "chapters": [
 *     { "chapter_num": 1, "chapter_title": "第1话" }
 *   ]
 * }
 */
work.post('/update', authMiddleware, requireRole('CRAWLER'), async (c) => {
  let body: Record<string, unknown>;
  try {
    body = (await c.req.json()) as Record<string, unknown>;
  } catch {
    return errorResponse(c, '请求体不是合法的 JSON', 400);
  }

  // 兼容 CLI 的包装格式 { work: { ... }, chapters: [...] }
  if (typeof body.work === 'object' && body.work !== null) {
    const w = body.work as Record<string, unknown>;
    body = { ...w, chapters: body.chapters ?? w.chapters ?? [] };
  }

  const title = body.title as string | undefined;
  const category = body.category as string | undefined;
  const description = body.description as string | undefined;
  const cover_r2_path = body.cover_r2_path as string | undefined;
  const source = body.source as string | undefined;
  const source_url = body.source_url as string | undefined;
  const status = body.status as string | undefined;
  const chapters = body.chapters as unknown[] | undefined;

  if (!title || typeof title !== 'string') {
    return errorResponse(c, 'title 不能为空', 400);
  }

  // 1. 查找已有作品：优先按 source_url，其次按 title
  let existing: WorkRow | null = null;
  if (source_url) {
    existing = await c.env.DB.prepare('SELECT * FROM works WHERE source_url = ?')
      .bind(source_url)
      .first<WorkRow>();
  }
  if (!existing) {
    existing = await c.env.DB.prepare('SELECT * FROM works WHERE title = ?')
      .bind(title)
      .first<WorkRow>();
  }

  // 2. 新增或更新作品
  let workId: number;
  const workStatus = status || 'ongoing';

  if (existing) {
    workId = existing.id;
    await c.env.DB.prepare(
      'UPDATE works SET title = ?, category = ?, description = ?, cover_r2_path = ?, source = ?, source_url = ?, status = ? WHERE id = ?',
    )
      .bind(
        title,
        category ?? existing.category,
        description ?? existing.description,
        cover_r2_path ?? existing.cover_r2_path,
        source ?? existing.source,
        source_url ?? existing.source_url,
        workStatus,
        workId,
      )
      .run();
  } else {
    const insertRes = await c.env.DB.prepare(
      'INSERT INTO works (title, category, description, cover_r2_path, source, source_url, status) VALUES (?, ?, ?, ?, ?, ?, ?)',
    )
      .bind(title, category ?? null, description ?? null, cover_r2_path ?? null, source ?? null, source_url ?? null, workStatus)
      .run();
    workId = insertRes.meta.last_row_id as number;
  }

  // 3. 批量处理章节（避免逐个查询的超限问题）
  let latestChapterNum = existing?.latest_chapter_num ?? 0;

  if (Array.isArray(chapters) && chapters.length > 0) {
    // 一次性查出已有章节
    const existingCh = await c.env.DB.prepare(
      'SELECT chapter_num, id, chapter_title FROM chapters WHERE work_id = ?',
    ).bind(workId).all<{ chapter_num: number; id: number; chapter_title: string | null }>();
    const existingMap = new Map(
      existingCh.results.map((r: any) => [r.chapter_num, r]),
    );

    const inserts: import('@cloudflare/workers-types').D1PreparedStatement[] = [];
    const updates: import('@cloudflare/workers-types').D1PreparedStatement[] = [];

    for (const ch of chapters) {
      const chObj = ch as Record<string, unknown>;
      if (!chObj || typeof chObj.chapter_num !== 'number') continue;
      const num = chObj.chapter_num as number;
      const title = (chObj.chapter_title as string) ?? null;
      const exist = existingMap.get(num);

      if (exist) {
        if (title !== null && title !== exist.chapter_title) {
          updates.push(
            c.env.DB.prepare('UPDATE chapters SET chapter_title = ? WHERE id = ?')
              .bind(title, exist.id),
          );
        }
      } else {
        inserts.push(
          c.env.DB.prepare('INSERT INTO chapters (work_id, chapter_num, chapter_title) VALUES (?, ?, ?)')
            .bind(workId, num, title),
        );
      }

      if (num > latestChapterNum) latestChapterNum = num;
    }

    const batch = [...inserts, ...updates];
    if (batch.length > 0) {
      // 分批每批最多 100 条
      for (let i = 0; i < batch.length; i += 100) {
        await c.env.DB.batch(batch.slice(i, i + 100));
      }
    }

    await c.env.DB.prepare('UPDATE works SET latest_chapter_num = ? WHERE id = ?')
      .bind(latestChapterNum, workId)
      .run();
  }

  // 无论上传的 chapters 是否为空，都根据 chapters 表的实际数据同步 latest_chapter_num
  const actualMaxRes = await c.env.DB.prepare(
    'SELECT MAX(chapter_num) as max_num FROM chapters WHERE work_id = ?',
  ).bind(workId).first<{ max_num: number | null }>();
  const actualMax = actualMaxRes?.max_num ?? 0;
  if (actualMax !== latestChapterNum) {
    await c.env.DB.prepare('UPDATE works SET latest_chapter_num = ? WHERE id = ?')
      .bind(actualMax, workId)
      .run();
    latestChapterNum = actualMax;
  }

  return successResponse(
    c,
    {
      work_id: workId,
      latest_chapter_num: latestChapterNum,
      chapter_count: Array.isArray(chapters) ? chapters.length : 0,
    },
    existing ? '作品更新成功' : '作品新增成功',
  );
});

/**
 * POST /api/work/import  （需 CRAWLER 或 USER 权限）
 * 通过 source_url 直接导入作品（手机端搜索后可直接导入）。
 * - Worker 能爬的源（mh160mh / tencent / guazi / kuaikan）：Worker 端直接爬取并写入 D1。
 * - Worker 爬不了的源（bilibili 需浏览器 / godamh 需 TLS 伪装）：
 *   若已配置 VPS_URL，转发给 VPS crawler-daemon 爬取并回写 D1；
 *   若未配置 VPS_URL，返回 400 提示需 VPS 或本地 CLI。
 *
 * Body: { "source_url": "https://www.mh160mh.com/kanmanhua/94/" }
 */
work.post('/import', authMiddleware, requireRole('CRAWLER', 'USER'), async (c) => {
  let body: { source_url?: string };
  try {
    body = (await c.req.json()) as { source_url?: string };
  } catch {
    return errorResponse(c, '请求体不是合法的 JSON', 400);
  }

  const sourceUrl = (body.source_url || '').trim();
  if (!sourceUrl) {
    return errorResponse(c, 'source_url 不能为空', 400);
  }

  const crawler = resolveSource(sourceUrl);
  if (!crawler) {
    // Worker 无法爬取该源（需浏览器渲染 / TLS 伪装）。
    // 若已配置 VPS crawler-daemon，则转发给 VPS 处理；否则返回原 400 错误。
    const vpsBaseUrl = await getVpsUrl(c.env.DB, c.env.VPS_URL);
    if (!vpsBaseUrl) {
      return errorResponse(
        c,
        `Worker 不支持该源（可能需浏览器渲染或 TLS 伪装，请用 VPS crawler-daemon 或本地 CLI）: ${sourceUrl}`,
        400,
      );
    }

    try {
      const data = await fetchVpsJson(vpsBaseUrl, '/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: sourceUrl }),
      });
      return c.json(data);
    } catch {
      return errorResponse(c, 'VPS 导入服务不可达', 502, 502, null);
    }
  }

  let crawlResult: CrawlResult;
  try {
    crawlResult = await crawler.crawl(sourceUrl);
  } catch (e) {
    return errorResponse(
      c,
      `爬取失败: ${e instanceof Error ? e.message : String(e)}`,
      500,
      500,
    );
  }

  const existing = await c.env.DB.prepare('SELECT id, cover_r2_path FROM works WHERE source_url = ?')
    .bind(sourceUrl)
    .first<{ id: number; cover_r2_path: string | null }>();

  let workId: number;
  if (existing) {
    workId = existing.id;
    await c.env.DB.prepare(
      'UPDATE works SET title = ?, source = ?, status = ? WHERE id = ?',
    )
      .bind(crawlResult.title, crawler.name, crawlResult.status, workId)
      .run();
  } else {
    const ins = await c.env.DB.prepare(
      'INSERT INTO works (title, source, source_url, status) VALUES (?, ?, ?, ?)',
    )
      .bind(crawlResult.title, crawler.name, sourceUrl, crawlResult.status)
      .run();
    workId = ins.meta.last_row_id as number;
  }

  const existingCh = await c.env.DB.prepare(
    'SELECT chapter_num FROM chapters WHERE work_id = ?',
  ).bind(workId).all<{ chapter_num: number }>();
  const existingSet = new Set(existingCh.results.map((r) => r.chapter_num));
  const newChapters = crawlResult.chapters.filter(
    (ch) => !existingSet.has(ch.chapter_num),
  );

  if (newChapters.length > 0) {
    const inserts = newChapters.map((ch) =>
      c.env.DB.prepare(
        'INSERT INTO chapters (work_id, chapter_num, chapter_title) VALUES (?, ?, ?)',
      ).bind(workId, ch.chapter_num, ch.chapter_title),
    );
    for (let i = 0; i < inserts.length; i += 100) {
      await c.env.DB.batch(inserts.slice(i, i + 100));
    }
  }

  const maxRes = await c.env.DB.prepare(
    'SELECT MAX(chapter_num) as max_num FROM chapters WHERE work_id = ?',
  ).bind(workId).first<{ max_num: number | null }>();
  await c.env.DB.prepare('UPDATE works SET latest_chapter_num = ? WHERE id = ?')
    .bind(maxRes?.max_num ?? 0, workId)
    .run();

  // 回填封面：作品尚无封面时下载源站封面并上传 R2（与 VPS daemon 流程一致）
  let coverR2Path = existing?.cover_r2_path ?? null;
  if (!coverR2Path && crawlResult.cover_url) {
    const uploaded = await uploadCoverToR2(c.env, workId, crawlResult.cover_url);
    if (uploaded) {
      coverR2Path = uploaded;
      await c.env.DB.prepare('UPDATE works SET cover_r2_path = ? WHERE id = ?')
        .bind(coverR2Path, workId)
        .run();
    }
  }

  return successResponse(
    c,
    {
      work_id: workId,
      title: crawlResult.title,
      source: crawler.name,
      chapter_count: crawlResult.chapters.length,
      new_chapters: newChapters.length,
      cover_r2_path: coverR2Path,
    },
    existing ? '作品已存在，已更新章节' : '导入成功',
  );
});

/**
 * POST /api/work/delete  （需 CRAWLER 权限）
 * 删除作品及其所有关联数据
 * Body: { id }
 */
work.post('/delete', authMiddleware, async (c) => {
  let body: { id?: number };
  try {
    body = (await c.req.json()) as { id?: number };
  } catch {
    return errorResponse(c, '请求体不是合法的 JSON', 400);
  }

  const { id } = body;

  if (!id || typeof id !== 'number') {
    return errorResponse(c, 'id 不能为空', 400);
  }

  const existing = await c.env.DB.prepare('SELECT id FROM works WHERE id = ?')
    .bind(id)
    .first<{ id: number }>();

  if (!existing) {
    return errorResponse(c, '作品不存在', 404, 404);
  }

  await c.env.DB.batch([
    c.env.DB.prepare('DELETE FROM user_bookmark WHERE work_id = ?').bind(id),
    c.env.DB.prepare('DELETE FROM chapters WHERE work_id = ?').bind(id),
    c.env.DB.prepare('DELETE FROM works WHERE id = ?').bind(id),
  ]);

  return successResponse(c, null, '作品已删除');
});

export default work;
