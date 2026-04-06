import fs from 'fs/promises';
import path from 'path';
import crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SERVER_ROOT = path.resolve(__dirname, '../..');

const CACHE_DIR = path.join(SERVER_ROOT, '.cache');
const IMAGES_DIR = path.join(CACHE_DIR, 'images');
const AUDIO_DIR = path.join(CACHE_DIR, 'audio');
const TTL_MS = 24 * 60 * 60 * 1000; // 24 hours
const CLEANUP_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

// Ensure cache directories exist
async function ensureCacheDirectories(): Promise<void> {
  await fs.mkdir(IMAGES_DIR, { recursive: true });
  await fs.mkdir(AUDIO_DIR, { recursive: true });
}

// Generate hash for cache key
export function generateCacheKey(input: string): string {
  return crypto.createHash('sha256').update(input).digest('hex');
}

// Store data in cache
export async function cacheImage(key: string, data: Buffer): Promise<string> {
  await ensureCacheDirectories();
  const fileName = `${key}.png`;
  const filePath = path.join(IMAGES_DIR, fileName);
  await fs.writeFile(filePath, data);
  return filePath;
}

export async function cacheAudio(key: string, data: Buffer): Promise<string> {
  await ensureCacheDirectories();
  const fileName = `${key}.mp3`;
  const filePath = path.join(AUDIO_DIR, fileName);
  await fs.writeFile(filePath, data);
  return filePath;
}

// Get cached file path if exists and not expired
export async function getCachedImage(key: string): Promise<string | null> {
  const fileName = `${key}.png`;
  const filePath = path.join(IMAGES_DIR, fileName);

  try {
    const stats = await fs.stat(filePath);
    const age = Date.now() - stats.mtimeMs;

    if (age > TTL_MS) {
      // Expired, delete it
      await fs.unlink(filePath).catch(() => {});
      return null;
    }

    return filePath;
  } catch (error) {
    return null;
  }
}

export async function getCachedAudio(key: string): Promise<string | null> {
  const fileName = `${key}.mp3`;
  const filePath = path.join(AUDIO_DIR, fileName);

  try {
    const stats = await fs.stat(filePath);
    const age = Date.now() - stats.mtimeMs;

    if (age > TTL_MS) {
      // Expired, delete it
      await fs.unlink(filePath).catch(() => {});
      return null;
    }

    return filePath;
  } catch (error) {
    return null;
  }
}

// Clean up expired cache files
async function cleanupExpiredFiles(directory: string): Promise<void> {
  try {
    // Ensure directory exists before trying to read it
    await fs.mkdir(directory, { recursive: true });

    const files = await fs.readdir(directory);
    const now = Date.now();

    for (const file of files) {
      const filePath = path.join(directory, file);
      try {
        const stats = await fs.stat(filePath);
        const age = now - stats.mtimeMs;

        if (age > TTL_MS) {
          await fs.unlink(filePath);
          console.log(`Cleaned up expired cache file: ${file}`);
        }
      } catch (error) {
        // File might have been deleted already, ignore
      }
    }
  } catch (error) {
    console.error(`Error cleaning up ${directory}:`, error);
  }
}

async function runCleanup(): Promise<void> {
  await cleanupExpiredFiles(IMAGES_DIR);
  await cleanupExpiredFiles(AUDIO_DIR);
}

// Start scheduled cleanup
export function startCleanupSchedule(): NodeJS.Timeout {
  console.log('Starting cache cleanup schedule (every hour)');
  // Run cleanup immediately on start
  runCleanup().catch(console.error);
  // Then schedule periodic cleanup
  return setInterval(() => {
    runCleanup().catch(console.error);
  }, CLEANUP_INTERVAL_MS);
}

// Stop scheduled cleanup
export function stopCleanupSchedule(interval: NodeJS.Timeout): void {
  clearInterval(interval);
}
