import type { Request, Response, NextFunction } from 'express';

const SESSION_ID_REGEX = /^[a-zA-Z0-9_-]{8,64}$/;

export function isValidSessionId(id: unknown): id is string {
  return typeof id === 'string' && SESSION_ID_REGEX.test(id);
}

export function validateSessionId(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const { id } = req.params;
  if (!isValidSessionId(id)) {
    res.status(400).json({ error: 'Invalid session ID format' });
    return;
  }
  next();
}
