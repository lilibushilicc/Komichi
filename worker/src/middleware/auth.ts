/**
 * 认证与鉴权中间件
 * - authMiddleware: 解析并校验 JWT，将用户信息写入上下文
 * - requireRole:   校验用户是否具备指定角色
 */
import type { MiddlewareHandler } from 'hono';
import type { AppEnv, JwtPayload } from '../types';
import { verifyJwt } from '../utils/jwt';
import { errorResponse } from '../utils/response';

/**
 * JWT 认证中间件
 * 从 Authorization: Bearer <token> 头部提取并校验 token
 */
export const authMiddleware: MiddlewareHandler<AppEnv> = async (c, next) => {
  const authHeader = c.req.header('Authorization') || '';
  const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7).trim() : '';

  if (!token) {
    return errorResponse(c, '未提供认证 token', 401, 401);
  }

  const payload = await verifyJwt(token, c.env.JWT_SECRET);
  if (!payload) {
    return errorResponse(c, 'token 无效或已过期', 401, 401);
  }

  const user: JwtPayload = {
    sub: Number(payload.sub),
    username: String(payload.username ?? ''),
    role: String(payload.role ?? ''),
    iat: Number(payload.iat ?? 0),
    exp: Number(payload.exp ?? 0),
  };

  c.set('user', user);
  await next();
};

/**
 * 角色校验中间件工厂
 * 需在 authMiddleware 之后使用
 * @param roles 允许通过的角色列表
 */
export function requireRole(...roles: string[]): MiddlewareHandler<AppEnv> {
  return async (c, next) => {
    const user = c.get('user');
    if (!user) {
      return errorResponse(c, '未认证', 401, 401);
    }
    if (!roles.includes(user.role)) {
      return errorResponse(c, '权限不足，需要角色: ' + roles.join(' / '), 403, 403);
    }
    await next();
  };
}
