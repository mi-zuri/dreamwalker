import { Router } from 'express';
import { getCachedImage, getCachedAudio } from '../services/cache.js';

const router = Router();

// GET /api/media/images/:key - Serve cached images
router.get('/images/:key', async (req, res) => {
  const { key } = req.params;

  if (!key || !/^[a-f0-9]{64}$/.test(key)) {
    res.status(400).json({ error: 'Invalid image key' });
    return;
  }

  try {
    const filePath = await getCachedImage(key);

    if (!filePath) {
      res.status(404).json({ error: 'Image not found or expired' });
      return;
    }

    // Read and send file manually to avoid sendFile path issues
    const fs = await import('fs/promises');
    const fileBuffer = await fs.readFile(filePath);
    res.setHeader('Cache-Control', 'public, max-age=86400');
    res.setHeader('Content-Type', 'image/png');
    res.send(fileBuffer);
  } catch (error) {
    console.error('Error serving image:', error);
    res.status(500).json({ error: 'Failed to serve image' });
  }
});

// GET /api/media/audio/:key - Serve cached audio
router.get('/audio/:key', async (req, res) => {
  const { key } = req.params;

  if (!key || !/^[a-f0-9]{64}$/.test(key)) {
    res.status(400).json({ error: 'Invalid audio key' });
    return;
  }

  try {
    const filePath = await getCachedAudio(key);

    if (!filePath) {
      res.status(404).json({ error: 'Audio not found or expired' });
      return;
    }

    // Read and send file manually
    const fs = await import('fs/promises');
    const fileBuffer = await fs.readFile(filePath);
    res.setHeader('Cache-Control', 'public, max-age=86400');
    res.setHeader('Content-Type', 'audio/mpeg');
    res.send(fileBuffer);
  } catch (error) {
    console.error('Error serving audio:', error);
    res.status(500).json({ error: 'Failed to serve audio' });
  }
});

export default router;
