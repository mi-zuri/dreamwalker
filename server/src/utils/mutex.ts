const locks = new Map<string, Promise<void>>();

export async function withSessionLock<T>(
  sessionId: string,
  fn: () => Promise<T>
): Promise<T> {
  const currentLock = locks.get(sessionId) ?? Promise.resolve();

  let releaseLock: () => void;
  const newLock = new Promise<void>((resolve) => {
    releaseLock = resolve;
  });

  locks.set(sessionId, newLock);

  await currentLock;

  try {
    return await fn();
  } finally {
    releaseLock!();
    if (locks.get(sessionId) === newLock) {
      locks.delete(sessionId);
    }
  }
}
