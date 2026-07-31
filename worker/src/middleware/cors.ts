/**
 * CORS 中间件
 * 私有化部署，允许所有来源访问。
 */
import type { MiddlewareHandler } from 'hono';
import type { AppEnv } from '../types';

export const corsMiddleware: MiddlewareHandler<AppEnv> = async (c, next) => {
  // 允许所有来源（私有化部署）
  c.header('Access-Control-Allow-Origin', '*');
  c.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  c.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With');
  c.header('Access-Control-Expose-Headers', 'Content-Length, Content-Type');
  c.header('Access-Control-Max-Age', '86400');

  // 处理预检请求
  if (c.req.method === 'OPTIONS') {
    return c.body(null, 204);
  }

  await next();
};
