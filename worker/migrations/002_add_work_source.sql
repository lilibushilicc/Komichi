-- 迁移 002：works 表增加 source 列（记录作品来自哪个爬虫源，如 godamh / mh160mh）
-- 使用方式: npx wrangler d1 execute komichi --file=./migrations/002_add_work_source.sql --remote
ALTER TABLE works ADD COLUMN source TEXT;

-- 回填：source_url 包含域名时按域名推断来源
UPDATE works SET source = 'godamh'  WHERE source LIKE '%godamh.com%'  AND (source IS NULL OR source = '');
UPDATE works SET source = 'mh160mh' WHERE source LIKE '%mh160mh.com%' AND (source IS NULL OR source = '');
