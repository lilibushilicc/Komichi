/**
 * 统一响应工具
 * 所有接口返回统一格式: { code, msg, data }
 */
import type { Context } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import type { AppEnv, ApiResponse } from '../types';

/** 构造成功响应体 */
export function success<T = unknown>(data: T = {} as T, msg = 'success'): ApiResponse<T> {
  return { code: 200, msg, data };
}

/** 构造失败响应体 */
export function fail(msg = 'error', code = 400, data: unknown = {}): ApiResponse {
  return { code, msg, data };
}

/** 返回 JSON 成功响应 */
export function successResponse<T = unknown>(
  c: Context<AppEnv>,
  data: T = {} as T,
  msg = 'success',
) {
  return c.json<ApiResponse<T>>({ code: 200, msg, data });
}

/** 返回 JSON 错误响应，可指定 HTTP 状态码与业务码 */
export function errorResponse(
  c: Context<AppEnv>,
  msg = 'error',
  code = 400,
  httpStatus: number = code,
  data: unknown = {},
) {
  return c.json<ApiResponse>({ code, msg, data }, httpStatus as ContentfulStatusCode);
}
