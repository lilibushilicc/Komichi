/**
 * 阅读记录路由（全部需要 USER JWT 认证）
 * - GET  /api/bookmark/list    获取用户阅读记录列表
 * - POST /api/bookmark/save    保存/更新阅读进度
 * - POST /api/bookmark/delete  删除阅读记录
 */
import { Hono } from 'hono';
import type { AppEnv, JwtPayload, BookmarkRow } from '../types';
import { successResponse, errorResponse } from '../utils/response';
import { authMiddleware } from '../middleware/auth';

const bookmark = new Hono<AppEnv>();

// 全部阅读记录接口均需认证
bookmark.use('*', authMiddleware);

/**
 * GET /api/bookmark/list
 * 返回当前用户的阅读记录，关联作品信息
 */
bookmark.get('/list', async (c) => {
  const user = c.get('user') as JwtPayload;

  const res = await c.env.DB.prepare(
    `SELECT
       b.id, b.user_id, b.work_id, b.chapter_num, b.note, b.last_read_time,
       w.title, w.cover_r2_path, w.status, w.latest_chapter_num, w.category
     FROM user_bookmark b
     LEFT JOIN works w ON b.work_id = w.id
     WHERE b.user_id = ?
     ORDER BY b.last_read_time DESC`,
  )
    .bind(user.sub)
    .all<BookmarkRow & {
      title: string | null;
      cover_r2_path: string | null;
      status: string | null;
      latest_chapter_num: number | null;
      category: string | null;
    }>();

  return successResponse(c, { list: res.results });
});

/**
 * POST /api/bookmark/save
 * 保存或更新阅读进度
 * Body: { work_id, chapter_num, note? }
 */
bookmark.post('/save', async (c) => {
  const user = c.get('user') as JwtPayload;

  let body: { work_id?: number; chapter_num?: number; note?: string };
  try {
    body = (await c.req.json()) as { work_id?: number; chapter_num?: number; note?: string };
  } catch {
    return errorResponse(c, '请求体不是合法的 JSON', 400);
  }

  const { work_id, chapter_num, note } = body;

  if (!work_id || typeof work_id !== 'number') {
    return errorResponse(c, 'work_id 不能为空', 400);
  }

  // 校验作品是否存在
  const workExists = await c.env.DB.prepare('SELECT id FROM works WHERE id = ?')
    .bind(work_id)
    .first<{ id: number }>();
  if (!workExists) {
    return errorResponse(c, '作品不存在', 404, 404);
  }

  const chapterNum = typeof chapter_num === 'number' && chapter_num >= 0 ? chapter_num : 0;

  // upsert 阅读记录
  const existing = await c.env.DB.prepare(
    'SELECT id FROM user_bookmark WHERE user_id = ? AND work_id = ?',
  )
    .bind(user.sub, work_id)
    .first<{ id: number }>();

  if (existing) {
    await c.env.DB.prepare(
      `UPDATE user_bookmark
       SET chapter_num = ?, note = ?, last_read_time = CURRENT_TIMESTAMP
       WHERE id = ?`,
    )
      .bind(chapterNum, note ?? null, existing.id)
      .run();
    return successResponse(c, { bookmark_id: existing.id }, '阅读进度已更新');
  }

  const insertRes = await c.env.DB.prepare(
    `INSERT INTO user_bookmark (user_id, work_id, chapter_num, note, last_read_time)
     VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)`,
  )
    .bind(user.sub, work_id, chapterNum, note ?? null)
    .run();

  return successResponse(
    c,
    { bookmark_id: insertRes.meta.last_row_id },
    '阅读进度已保存',
  );
});

/**
 * POST /api/bookmark/delete
 * 删除用户的阅读记录
 * Body: { work_id }
 */
bookmark.post('/delete', async (c) => {
  const user = c.get('user') as JwtPayload;

  let body: { work_id?: number };
  try {
    body = (await c.req.json()) as { work_id?: number };
  } catch {
    return errorResponse(c, '请求体不是合法的 JSON', 400);
  }

  const { work_id } = body;

  if (!work_id || typeof work_id !== 'number') {
    return errorResponse(c, 'work_id 不能为空', 400);
  }

  const existing = await c.env.DB.prepare(
    'SELECT id FROM user_bookmark WHERE user_id = ? AND work_id = ?',
  )
    .bind(user.sub, work_id)
    .first<{ id: number }>();

  if (!existing) {
    return successResponse(c, null, '阅读记录不存在或已删除');
  }

  await c.env.DB.prepare('DELETE FROM user_bookmark WHERE id = ?')
    .bind(existing.id)
    .run();

  return successResponse(c, null, '阅读记录已删除');
});

export default bookmark;
