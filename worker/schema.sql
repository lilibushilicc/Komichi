-- ============================================================
-- Komichi 数据库建表语句
-- 使用方式: npx wrangler d1 execute komichi --file=./schema.sql
-- ============================================================

-- 用户表
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT DEFAULT 'USER',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 作品表
CREATE TABLE IF NOT EXISTS works(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  category TEXT,
  description TEXT,
  cover_r2_path TEXT,
  source TEXT,
  source_url TEXT,
  latest_chapter_num INTEGER DEFAULT 0,
  status TEXT DEFAULT 'ongoing',
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 章节表
CREATE TABLE IF NOT EXISTS chapters(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  work_id INTEGER NOT NULL,
  chapter_num INTEGER NOT NULL,
  chapter_title TEXT,
  create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 用户阅读记录表
CREATE TABLE IF NOT EXISTS user_bookmark(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  work_id INTEGER NOT NULL,
  chapter_num INTEGER DEFAULT 0,
  note TEXT,
  last_read_time TIMESTAMP
);

-- ============================================================
-- 索引
-- ============================================================

-- 作品状态过滤索引
CREATE INDEX IF NOT EXISTS idx_works_status ON works(status);

-- 作品创建时间排序索引
CREATE INDEX IF NOT EXISTS idx_works_create_time ON works(create_time);

-- source_url 查询索引（爬虫去重用）
CREATE INDEX IF NOT EXISTS idx_works_source_url ON works(source_url);

-- 章节-作品关联索引
CREATE INDEX IF NOT EXISTS idx_chapters_work_id ON chapters(work_id);

-- 章节 (work_id, chapter_num) 联合索引（爬虫章节去重用）
CREATE INDEX IF NOT EXISTS idx_chapters_work_chapter ON chapters(work_id, chapter_num);

-- 用户阅读记录索引
CREATE INDEX IF NOT EXISTS idx_user_bookmark_user_id ON user_bookmark(user_id);

-- 用户阅读记录 (user_id, work_id) 联合唯一索引（防止重复收藏）
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_bookmark_user_work ON user_bookmark(user_id, work_id);

-- 用户阅读记录最后阅读时间排序索引
CREATE INDEX IF NOT EXISTS idx_user_bookmark_last_read_time ON user_bookmark(last_read_time);
