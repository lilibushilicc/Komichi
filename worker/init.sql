-- ============================================================
-- Komichi 初始化数据 - 默认用户
-- 使用方式: npx wrangler d1 execute komichi --file=./init.sql
--
-- 默认账号（请部署后立即修改密码）:
--   USER 角色:     admin / admin123
--   CRAWLER 角色:  crawler / crawler123
--
-- 密码哈希算法: PBKDF2 + SHA-256, 100000 次迭代, 16 字节盐
-- 格式: pbkdf2$iterations$base64url(salt)$base64url(hash)
--
-- 注意: 哈希值由独立脚本生成，与 Worker 端 utils/jwt.ts 的 hashPassword 算法一致。
-- 若需重新生成，可运行: node scripts/genhash.js
-- ============================================================

INSERT INTO users (username, password_hash, role)
SELECT 'admin', 'pbkdf2$100000$9VvWJ0ZDdhdZQb9nu1iUOQ$Jb3ywJ5D5IJV-DUpeELD39nJrhhmjRyWD8W2UjPrnr8', 'USER'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');

INSERT INTO users (username, password_hash, role)
SELECT 'crawler', 'pbkdf2$100000$j88slQYrEDJ5R46uely3Sw$C4RVjegiBK83GkypK7JzQkhm1HFj75xuKMw3hQMvDHk', 'CRAWLER'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'crawler');
