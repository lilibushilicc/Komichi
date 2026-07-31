/**
 * 作品路由
 * - GET  /api/work/list       获取作品列表（分页 + status 过滤）
 * - GET  /api/work/check/:id  检查作品更新（最新章节信息）
 * - GET  /api/work/:id        获取作品详情（含章节列表）
 * - POST /api/work/update     新增/更新作品数据（需 CRAWLER 权限）
 *
 * 注意: 静态路由 (/list, /check/:id) 必须在参数路由 (/:id) 之前注册，
 *       以避免被参数路由捕获。
 */
import { Hono } from 'hono';
import type { AppEnv, WorkRow, ChapterRow } from '../types';
import { successResponse, errorResponse } from '../utils/response';
import { authMiddleware, requireRole } from '../middleware/auth';

const work = new Hono<AppEnv>();

/** 安全解析正整数，失败返回默认值 */
function parsePositiveInt(value: string | undefined, defaultValue: number): number {
  if (!value) return defaultValue;
  const n = parseInt(value, 10);
  return Number.isFinite(n) && n > 0 ? n : defaultValue;
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
    list: listRes.results,
    total: countRes?.total ?? 0,
    page,
    size: limitSize,
  });
});

/**
 * GET /api/work/check/:id
 * 返回作品最新章节信息，用于客户端检查更新
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

  const latestChapter = await c.env.DB.prepare(
    'SELECT * FROM chapters WHERE work_id = ? ORDER BY chapter_num DESC LIMIT 1',
  ).bind(id).first<ChapterRow>();

  return successResponse(c, {
    work: {
      id: workRow.id,
      title: workRow.title,
      latest_chapter_num: workRow.latest_chapter_num,
      status: workRow.status,
      source: workRow.source,
      source_url: workRow.source_url,
    },
    latest_chapter: latestChapter ?? null,
    has_update: latestChapter ? latestChapter.chapter_num >= workRow.latest_chapter_num : false,
  });
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
