import { Router, type Router as ExpressRouter, type Request, type Response } from "express";
import fs from "fs/promises";
import { getCachedMedia, type MediaKind } from "../services/cache.js";

const router: ExpressRouter = Router();

async function serve(kind: MediaKind, contentType: string, req: Request, res: Response) {
  const key = req.params.key as string;
  if (!/^[a-f0-9]{64}$/.test(key)) {
    res.status(400).json({ error: `Invalid ${kind} key` });
    return;
  }
  const filePath = await getCachedMedia(kind, key);
  if (!filePath) {
    res.status(404).json({ error: `${kind} not found or expired` });
    return;
  }
  res.setHeader("Cache-Control", "public, max-age=86400");
  res.setHeader("Content-Type", contentType);
  res.send(await fs.readFile(filePath));
}

router.get("/images/:key", (req, res) => serve("image", "image/png", req, res));
router.get("/audio/:key", (req, res) => serve("audio", "audio/mpeg", req, res));

export default router;
