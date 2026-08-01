/**
 * 系统设置工具
 * 从 D1 settings 表读写键值对配置。
 * 用于动态管理 VPS_URL 等配置，无需重新部署 Worker。
 */

/** 从 D1 settings 表读取指定 key 的值，不存在返回 null */
export async function getSetting(db: D1Database, key: string): Promise<string | null> {
  const row = await db.prepare('SELECT value FROM settings WHERE key = ?')
    .bind(key)
    .first<{ value: string | null }>();
  return row?.value ?? null;
}

/** 写入/更新 D1 settings 表中的键值对 */
export async function setSetting(db: D1Database, key: string, value: string): Promise<void> {
  await db.prepare(
    'INSERT INTO settings (key, value, update_time) VALUES (?, ?, CURRENT_TIMESTAMP) ' +
    'ON CONFLICT(key) DO UPDATE SET value = ?, update_time = CURRENT_TIMESTAMP',
  ).bind(key, value, value).run();
}

/**
 * 获取 VPS_URL：优先从 D1 settings 表读取，回退到 env 绑定。
 * 这样 CLI 可以动态更新 VPS_URL 而无需重新部署 Worker。
 */
export async function getVpsUrl(db: D1Database, envVpsUrl: string | undefined): Promise<string> {
  const dbValue = await getSetting(db, 'vps_url');
  const raw = dbValue || envVpsUrl || '';
  return raw.trim().replace(/\/+$/, '');
}
