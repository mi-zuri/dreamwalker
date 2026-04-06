import { useState, useEffect } from "react";

interface StartScreenProps {
  onStart: (initialThought?: string) => void;
  isLoading: boolean;
  isWaitingForImage: boolean;
}

export function StartScreen({
  onStart,
  isLoading,
  isWaitingForImage,
}: StartScreenProps) {
  const [thought, setThought] = useState("");
  const [zText, setZText] = useState("z");

  const loading = isLoading || isWaitingForImage;

  useEffect(() => {
    if (!loading) return;
    const frames = ["z", "zz", "zzz", "zzzz"];
    let i = 0;
    const interval = setInterval(() => {
      i = (i + 1) % frames.length;
      setZText(frames[i]);
    }, 600);
    return () => clearInterval(interval);
  }, [loading]);

  const handleStart = () => {
    onStart(thought.trim() || undefined);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleStart();
    }
  };

  return (
    <div className="h-screen flex items-center justify-center p-4 relative">
      <div className="starfield" />

      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <div className="relative">
            <div
              className="absolute inset-0 -m-20"
              style={{
                background:
                  "radial-gradient(circle, #05050a 0%, #05050a 30%, rgba(5,5,10,0.6) 60%, transparent 100%)",
              }}
            />
            <div className="text-gray-400 text-sm tracking-wider relative z-10">
              {zText}
            </div>
          </div>
        </div>
      )}

      {!loading && (
        <div className="ascii-box p-6 max-w-md w-full relative z-10">
          <div className="text-center mb-6">
            <h1 className="text-indigo-400 text-2xl tracking-widest">
              DREAMWALKER
            </h1>
          </div>

          <button
            onClick={handleStart}
            disabled={isLoading}
            className="ascii-btn w-full px-4 py-3 text-sm text-indigo-400 hover:text-indigo-300
                       border-indigo-800 hover:border-indigo-600 disabled:opacity-50"
          >
            [BEGIN DREAMING]
          </button>

          <div className="mt-4">
            <textarea
              value={thought}
              onChange={(e) => setThought(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="whisper it to the stars... "
              disabled={isLoading}
              className="w-full bg-transparent border border-gray-800 rounded px-3 py-2 text-sm
                         text-gray-300 placeholder-gray-600 focus:border-indigo-700 focus:outline-none
                         resize-none h-20"
            />
          </div>
        </div>
      )}
    </div>
  );
}
