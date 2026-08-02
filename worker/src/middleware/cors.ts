/**
 * CORS 中间件
 *
 * 跨域策略：
 * - 配置了 CORS_ALLOW_ORIGIN（逗号分隔白名单）时，仅允许列表内的 Origin 跨域，
 *   命中则反射该 Origin；未命中则不返回 ACAO 头，浏览器将拒绝跨域。
 * - 未配置时回退为 '*'（向后兼容私有化部署），但公网/多用户场景务必设置白名单。
 */
import type { MiddlewareHandler } from 'hono';
import type { AppEnv } from '../types';

export const corsMiddleware: MiddlewareHandler<AppEnv> = async (c, next) => {
  const allowedRaw = c.env.CORS_ALLOW_ORIGIN;
  const origin = c.req.header('Origin');

  let allowOrigin = '*';
  if (allowedRaw && allowedRaw.trim().length > 0) {
    const list = allowedRaw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    allowOrigin = origin && list.includes(origin) ? origin : '';
  }

  if (allowOrigin) {
    c.header('Access-Control-Allow-Origin', allowOrigin);
  }
  c.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  c.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
  c.header('Access-Control-Expose-Headers', 'Content-Length, Content-Type');
  c.header('Access-Control-Max-Age', '86400');

  // 处理预检请求
  if (c.req.method === 'OPTIONS') {
    return c.body(null, allowOrigin ? 204 : 403);
  }

  await next();
};
