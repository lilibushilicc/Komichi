/**
 * Komichi Worker 类型定义
 */

/** Cloudflare Workers 环境绑定 */
export interface Bindings {
  /** D1 数据库绑定 */
  DB: D1Database;
  /** R2 对象存储绑定（图片存储） */
  BUCKET: R2Bucket;
  /** JWT 签名密钥 */
  JWT_SECRET: string;
}

/** JWT 载荷结构 */
export interface JwtPayload {
  /** 用户 ID */
  sub: number;
  /** 用户名 */
  username: string;
  /** 角色: USER | CRAWLER */
  role: string;
  /** 签发时间（秒） */
  iat: number;
  /** 过期时间（秒） */
  exp: number;
}

/** Hono 应用环境（包含 Bindings 与上下文变量） */
export interface AppEnv {
  Bindings: Bindings;
  Variables: {
    /** 认证后写入上下文的用户信息 */
    user: JwtPayload;
  };
}

/** 用户表行 */
export interface UserRow {
  id: number;
  username: string;
  password_hash: string;
  role: string;
  create_time: string;
}

/** 作品表行 */
export interface WorkRow {
  id: number;
  title: string;
  category: string | null;
  cover_r2_path: string | null;
  source_url: string | null;
  latest_chapter_num: number;
  status: string;
  create_time: string;
}

/** 章节表行 */
export interface ChapterRow {
  id: number;
  work_id: number;
  chapter_num: number;
  chapter_title: string | null;
  create_time: string;
}

/** 用户阅读记录行 */
export interface BookmarkRow {
  id: number;
  user_id: number;
  work_id: number;
  chapter_num: number;
  note: string | null;
  last_read_time: string | null;
}

/** 统一响应结构 */
export interface ApiResponse<T = unknown> {
  code: number;
  msg: string;
  data: T;
}

/** 作品更新接口的章节载荷 */
export interface ChapterInput {
  chapter_num: number;
  chapter_title?: string;
}

/** 作品更新接口载荷 */
export interface WorkUpdateInput {
  id?: number;
  title: string;
  category?: string;
  cover_r2_path?: string;
  source_url?: string;
  status?: string;
  chapters?: ChapterInput[];
}

/** 角色常量 */
export const ROLE = {
  USER: 'USER',
  CRAWLER: 'CRAWLER',
} as const;
