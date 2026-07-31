-- ============================================================
-- 003: works 表增加作品简介字段
-- 使用方式: npx wrangler d1 execute komichi --file=./migrations/003_add_work_description.sql
-- ============================================================

ALTER TABLE works ADD COLUMN description TEXT;
