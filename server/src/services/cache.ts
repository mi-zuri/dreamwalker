import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SERVER_ROOT = path.resolve(__dirname, '../..');

const CACHE_DIR = path.join(SERVER_ROOT, '.cache');
const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours
const CLEANUP_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

export type MediaKind = 'image' | 'audio';

const KIND_DIRS: Record<MediaKind, string> = {
  image: path.join(CACHE_DIR, 'images'),
  audio: path.join(CACHE_DIR, 'audio'),
};

const KIND_EXTS: Record<MediaKind, string> = {
  image: 'png',
  audio: 'mp3',
};

function filePathFor(kind: MediaKind, key: string): string {
  return path.join(KIND_DIRS[kind], `${key}.${KIND_EXTS[kind]}`);
}

export function generateCacheKey(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

export async function cacheMedia(kind: MediaKind, key: string, data: Buffer): Promise<string> {
  await fs.mkdir(KIND_DIRS[kind], { recursive: true });
  const filePath = filePathFor(kind, key);
  await fs.writeFile(filePath, data);
  return filePath;
}

export async function getCachedMedia(kind: MediaKind, key: string): Promise<string | null> {
  const filePath = filePathFor(kind, key);
  try {
    const stats = await fs.stat(filePath);
    if (Date.now() - stats.mtimeMs > TTL_MS) {
      await fs.unlink(filePath).catch(() => {});
      return null;
    }
    return filePath;
  } catch {
    return null;
  }
}

async function runCleanup(): Promise<void> {
  const now = Date.now();
  for (const dir of Object.values(KIND_DIRS)) {
    try {
      await fs.mkdir(dir, { recursive: true });
      for (const file of await fs.readdir(dir)) {
        const filePath = path.join(dir, file);
        const stats = await fs.stat(filePath).catch(() => null);
        if (stats && now - stats.mtimeMs > TTL_MS) {
          await fs.unlink(filePath).catch(() => {});
        }
      }
    } catch (e) {
      console.error(`Cache cleanup ${dir}:`, e);
    }
  }
}

export function startCleanupSchedule(): NodeJS.Timeout {
  runCleanup().catch(console.error);
  return setInterval(() => runCleanup().catch(console.error), CLEANUP_INTERVAL_MS);
}
