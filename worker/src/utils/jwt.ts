/**
 * JWT 与密码哈希工具
 * - JWT: 使用 Web Crypto API (HMAC-SHA256)，不依赖外部库
 * - 密码: 使用 PBKDF2 + SHA-256
 *
 * 全部基于 Cloudflare Workers 原生 Web Crypto API 实现。
 */

const encoder = new TextEncoder();
const decoder = new TextDecoder();

/** PBKDF2 迭代次数 */
const PBKDF2_ITERATIONS = 100_000;
/** PBKDF2 派生密钥长度（bit） */
const PBKDF2_KEYLEN = 256;
/** 盐长度（字节） */
const SALT_BYTES = 16;

/* ----------------------- Base64URL 编解码 ----------------------- */

/** ArrayBuffer / Uint8Array -> base64url 字符串 */
export function base64url(input: ArrayBuffer | Uint8Array): string {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** base64url 字符串 -> Uint8Array */
export function base64urlDecode(input: string): Uint8Array {
  const padded = input.replace(/-/g, '+').replace(/_/g, '/');
  const pad = padded.length % 4;
  const b64 = pad ? padded + '='.repeat(4 - pad) : padded;
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/* ----------------------- JWT 签发与校验 ----------------------- */

/** 导入 HMAC 密钥 */
async function getHmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify'],
  );
}

/**
 * 签发 JWT
 * @param payload 业务载荷（自动追加 iat / exp）
 * @param secret  签名密钥
 * @param expiresIn 有效期（秒），默认 24 小时
 */
export async function signJwt(
  payload: Record<string, unknown>,
  secret: string,
  expiresIn: number = 86400,
): Promise<string> {
  const header = { alg: 'HS256', typ: 'JWT' };
  const now = Math.floor(Date.now() / 1000);
  const fullPayload = { ...payload, iat: now, exp: now + expiresIn };

  const headerB64 = base64url(encoder.encode(JSON.stringify(header)));
  const payloadB64 = base64url(encoder.encode(JSON.stringify(fullPayload)));
  const signingInput = `${headerB64}.${payloadB64}`;

  const key = await getHmacKey(secret);
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(signingInput));
  const sigB64 = base64url(sig);

  return `${signingInput}.${sigB64}`;
}

/**
 * 校验 JWT 并返回载荷
 * @returns 校验通过返回载荷对象，失败返回 null
 */
export async function verifyJwt(
  token: string,
  secret: string,
): Promise<Record<string, unknown> | null> {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  const [headerB64, payloadB64, sigB64] = parts;
  const signingInput = `${headerB64}.${payloadB64}`;

  const key = await getHmacKey(secret);
  const sigBytes = base64urlDecode(sigB64);
  const valid = await crypto.subtle.verify('HMAC', key, sigBytes, encoder.encode(signingInput));
  if (!valid) return null;

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(decoder.decode(base64urlDecode(payloadB64)));
  } catch {
    return null;
  }

  // 校验过期时间
  if (typeof payload.exp === 'number' && Math.floor(Date.now() / 1000) > payload.exp) {
    return null;
  }
  return payload;
}

/* ----------------------- 密码哈希（PBKDF2） ----------------------- */

/**
 * 对密码进行 PBKDF2 + SHA-256 哈希
 * @param password 明文密码
 * @param salt     可选盐（Uint8Array），未提供时随机生成
 * @returns 格式: pbkdf2$iterations$base64url(salt)$base64url(hash)
 */
export async function hashPassword(
  password: string,
  salt?: Uint8Array,
): Promise<string> {
  const saltBytes = salt ?? crypto.getRandomValues(new Uint8Array(SALT_BYTES));

  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    encoder.encode(password),
    'PBKDF2',
    false,
    ['deriveBits'],
  );

  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt: saltBytes, iterations: PBKDF2_ITERATIONS, hash: 'SHA-256' },
    keyMaterial,
    PBKDF2_KEYLEN,
  );

  const saltB64 = base64url(saltBytes);
  const hashB64 = base64url(bits);
  return `pbkdf2$${PBKDF2_ITERATIONS}$${saltB64}$${hashB64}`;
}

/**
 * 校验明文密码与存储的哈希是否匹配
 * @param password 明文密码
 * @param stored   存储的哈希字符串 (pbkdf2$...)
 */
export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const parts = stored.split('$');
  if (parts.length !== 4 || parts[0] !== 'pbkdf2') return false;

  const iterations = parseInt(parts[1], 10);
  if (!Number.isFinite(iterations) || iterations <= 0) return false;

  let saltBytes: Uint8Array;
  let expectedHash: string;
  try {
    saltBytes = base64urlDecode(parts[2]);
    expectedHash = parts[3];
  } catch {
    return false;
  }

  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    encoder.encode(password),
    'PBKDF2',
    false,
    ['deriveBits'],
  );

  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', salt: saltBytes, iterations, hash: 'SHA-256' },
    keyMaterial,
    PBKDF2_KEYLEN,
  );

  const actualHash = base64url(bits);
  // 常量时间字符串比较，避免计时攻击
  return timingSafeEqual(actualHash, expectedHash);
}

/** 常量时间字符串比较 */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}
