/**
 * R2 签名路由
 * - GET /api/r2/sign   生成 R2 临时访问 URL（需认证）
 * - GET /api/r2/proxy  通过 Worker 代理读取 R2 对象（校验签名 token）
 *
 * 实现说明:
 *   Cloudflare Workers 的 R2 绑定不直接支持 S3 风格 presigned URL，
 *   本方案采用「Worker 代理 + 签名 token」方式：
 *   /sign  返回一个带过期时间的签名 URL（指向 /proxy），
 *   /proxy 校验 token 后直接从 R2 绑定流式返回对象。
 *   这样无需暴露 S3 access key，且完全运行在 Workers 内。
 */
import { Hono } from 'hono';
import type { AppEnv } from '../types';
import { successResponse, errorResponse } from '../utils/response';
import { authMiddleware, requireRole } from '../middleware/auth';
import { signJwt, verifyJwt } from '../utils/jwt';

const r2 = new Hono<AppEnv>();

/** 签名 URL 有效期（秒） */
const SIGN_EXPIRE_SECONDS = 3600;

/** 根据扩展名推断 Content-Type */
function guessContentType(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() ?? '';
  const map: Record<string, string> = {
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    png: 'image/png',
    gif: 'image/gif',
    webp: 'image/webp',
    bmp: 'image/bmp',
    avif: 'image/avif',
  };
  return map[ext] ?? 'application/octet-stream';
}

/**
 * GET /api/r2/sign?path=<r2_path>
 * 生成带签名的临时访问 URL
 */
r2.get('/sign', authMiddleware, async (c) => {
  const path = c.req.query('path')?.trim() || '';
  if (!path) {
    return errorResponse(c, 'path 参数不能为空', 400);
  }

  // 签发一个专用于 R2 代理访问的 token（载荷含 path 与 exp）
  const token = await signJwt({ path, type: 'r2proxy' }, c.env.JWT_SECRET, SIGN_EXPIRE_SECONDS);

  const baseUrl = new URL(c.req.url).origin;
  const url = `${baseUrl}/api/r2/proxy?path=${encodeURIComponent(path)}&token=${token}`;

  return successResponse(c, {
    url,
    path,
    expire: SIGN_EXPIRE_SECONDS,
    expire_at: Math.floor(Date.now() / 1000) + SIGN_EXPIRE_SECONDS,
  });
});

/**
 * GET /api/r2/proxy?path=<r2_path>&token=<signed_token>
 * 校验签名 token 后从 R2 流式返回对象
 */
r2.get('/proxy', async (c) => {
  const path = c.req.query('path')?.trim() || '';
  const token = c.req.query('token')?.trim() || '';

  if (!path || !token) {
    return errorResponse(c, 'path 和 token 参数不能为空', 400);
  }

  // 校验 token
  const payload = await verifyJwt(token, c.env.JWT_SECRET);
  if (!payload) {
    return errorResponse(c, '签名无效或已过期', 401, 401);
  }
  // 校验 token 类型与 path 一致，防止越权访问其他资源
  if (payload.type !== 'r2proxy' || payload.path !== path) {
    return errorResponse(c, '签名与请求路径不匹配', 403, 403);
  }

  // 从 R2 读取对象
  const object = await c.env.BUCKET.get(path);
  if (!object) {
    return errorResponse(c, '资源不存在', 404, 404);
  }

  const headers = new Headers();
  // 写入 R2 存储的 HTTP 元数据（如 contentType）
  object.writeHttpMetadata(headers);
  // 兜底：若无 content-type 则按扩展名推断
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', guessContentType(path));
  }
  headers.set('Cache-Control', 'public, max-age=86400');
  headers.set('ETag', object.httpEtag);

  // Hono 的 c.body 第三参要求 HeaderRecord（普通对象），需从 Headers 转换
  const headerRecord: Record<string, string> = {};
  headers.forEach((value, key) => {
    headerRecord[key] = value;
  });

  return c.body(object.body, 200, headerRecord);
});

/**
 * POST /api/r2/upload
 * 上传图片到 R2（需 CRAWLER 权限）
 * Body: multipart/form-data, 字段: file (文件), key (R2 对象键)
 */
r2.post('/upload', authMiddleware, requireRole('CRAWLER'), async (c) => {
  const formData = await c.req.formData();
  const file = formData.get('file');
  const key = formData.get('key')?.toString();

  if (!file || typeof file === 'string') {
    return errorResponse(c, 'file 字段不能为空或类型错误', 400);
  }
  if (!key) {
    return errorResponse(c, 'key 字段不能为空', 400);
  }

  const arrayBuffer = await file.arrayBuffer();
  await c.env.BUCKET.put(key, arrayBuffer, {
    httpMetadata: { contentType: file.type || 'application/octet-stream' },
  });

  return successResponse(c, { r2_path: key });
});

export default r2;
