/**
 * 认证路由
 * - POST /api/auth/login  用户登录，返回 JWT
 * - POST /api/auth/init   首次部署初始化默认账号（仅当 users 表为空时可用）
 */
import { Hono } from 'hono';
import type { AppEnv, UserRow } from '../types';
import { successResponse, errorResponse } from '../utils/response';
import { signJwt, verifyPassword, hashPassword } from '../utils/jwt';
import { rateLimit } from '../middleware/rateLimit';

const auth = new Hono<AppEnv>();

/** 解析请求体 JSON，失败返回空对象 */
async function parseBody<T = Record<string, unknown>>(c: { req: { json(): Promise<unknown> } }): Promise<T> {
  try {
    return (await c.req.json()) as T;
  } catch {
    return {} as T;
  }
}

/**
 * POST /api/auth/login
 * Body: { username, password }
 * 返回 JWT token
 */
auth.post('/login', rateLimit({ keyPrefix: 'login', windowSec: 60, max: 10 }), async (c) => {
  const { username, password } = await parseBody<{ username?: string; password?: string }>(c);

  if (!username || !password) {
    return errorResponse(c, '用户名和密码不能为空', 400);
  }

  const user = await c.env.DB.prepare('SELECT * FROM users WHERE username = ?')
    .bind(username)
    .first<UserRow>();

  if (!user) {
    return errorResponse(c, '用户名或密码错误', 401, 401);
  }

  const valid = await verifyPassword(password, user.password_hash);
  if (!valid) {
    return errorResponse(c, '用户名或密码错误', 401, 401);
  }

  const token = await signJwt(
    { sub: user.id, username: user.username, role: user.role },
    c.env.JWT_SECRET,
    7 * 24 * 3600, // 7 天有效期
  );

  return successResponse(c, {
    token,
    user: {
      id: user.id,
      username: user.username,
      role: user.role,
    },
  }, '登录成功');
});

/**
 * POST /api/auth/init
 * 首次部署初始化默认账号。
 * 仅当 users 表为空时可调用，创建：
 *   - admin / admin123      (USER 角色)
 *   - crawler / crawler123  (CRAWLER 角色)
 * 调用后请立即修改默认密码。
 */
auth.post('/init', async (c) => {
  const countRes = await c.env.DB.prepare('SELECT COUNT(*) as cnt FROM users').first<{ cnt: number }>();
  if (countRes && countRes.cnt > 0) {
    return errorResponse(c, '系统已初始化，禁止重复初始化', 400);
  }

  const adminHash = await hashPassword('admin123');
  const crawlerHash = await hashPassword('crawler123');

  await c.env.DB.batch([
    c.env.DB.prepare(
      'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
    ).bind('admin', adminHash, 'USER'),
    c.env.DB.prepare(
      'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
    ).bind('crawler', crawlerHash, 'CRAWLER'),
  ]);

  return successResponse(
    c,
    {
      accounts: [
        { username: 'admin', password: 'admin123', role: 'USER' },
        { username: 'crawler', password: 'crawler123', role: 'CRAWLER' },
      ],
    },
    '初始化成功，请及时修改默认密码',
  );
});

export default auth;
