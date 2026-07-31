/**
 * 生成 PBKDF2 密码哈希工具
 * 与 Worker 端 src/utils/jwt.ts 的 hashPassword 算法一致。
 *
 * 用法:
 *   node scripts/genhash.js              # 生成默认账号哈希
 *   node scripts/genhash.js mypassword   # 生成指定密码哈希
 *
 * 输出可直接写入 init.sql 的 password_hash 字段。
 */
const crypto = require('crypto');

function base64url(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function gen(password) {
  const salt = crypto.randomBytes(16);
  const iterations = 100000;
  const hash = crypto.pbkdf2Sync(password, salt, iterations, 32, 'sha256');
  return `pbkdf2$${iterations}$${base64url(salt)}$${base64url(hash)}`;
}

const targets = process.argv.slice(2);
const list = targets.length > 0 ? targets : ['admin123', 'crawler123'];

for (const pwd of list) {
  console.log(`${pwd}\t=>\t${gen(pwd)}`);
}
