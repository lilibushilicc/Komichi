/**
 * 速率限制中间件（固定窗口计数器）
 *
 * 通过 Cloudflare KV 记录「客户端 IP + 端点」在固定时间窗内的请求数，
 * 超过上限返回 429，用于防止：
 *   - /search 代理被滥用（对 VPS 造成 DoS）
 *   - /login 被爆破
 *
 * 优雅降级（不影响现有部署）：
 *   - 未配置 RATE_LIMIT KV 绑定时自动放行。
 *   - KV 读写异常时放行，避免限流自身成为故障点。
 */
import type { MiddlewareHandler } from 'hono';
import type { AppEnv } from '../types';

export interface RateLimitOptions {
  /** 限流键前缀，用于区分不同端点（如 'search' / 'login'） */
  keyPrefix: string;
  /** 时间窗（秒） */
  windowSec: number;
  /** 时间窗内允许的最大请求数 */
  max: number;
}

export function rateLimit(opts: RateLimitOptions): MiddlewareHandler<AppEnv> {
  return async (c, next) => {
    const kv = c.env.RATE_LIMIT;
    if (!kv) {
      await next();
      return;
    }

    const clientIp =
      c.req.header('CF-Connecting-IP') ||
      c.req.header('X-Forwarded-For')?.split(',')[0].trim() ||
      'unknown';
    const now = Math.floor(Date.now() / 1000);
    const windowStart = now - (now % opts.windowSec);
    const counterKey = `ratelimit:${opts.keyPrefix}:${clientIp}:${windowStart}`;

    try {
      const raw = await kv.get(counterKey);
      const count = raw ? parseInt(raw, 10) : 0;
      if (count >= opts.max) {
        c.header('Retry-After', String(opts.windowSec));
        return c.json(
          { code: 429, msg: '请求过于频繁，请稍后再试', data: null },
          429,
        );
      }
      await kv.put(counterKey, String(count + 1), {
        expirationTtl: opts.windowSec + 5,
      });
    } catch {
      // KV 异常：放行，不阻断正常请求
    }

    await next();
  };
}
