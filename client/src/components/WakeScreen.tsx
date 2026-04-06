import type { WakeCause } from '../../../shared/types';

interface WakeScreenProps {
  cause: WakeCause;
  steps: number;
  onRestart: () => void;
}

const causeLabels: Record<WakeCause, { title: string; desc: string }> = {
  emotional_overload: {
    title: 'EMOTIONAL_OVERLOAD',
    desc: 'feelings became too intense',
  },
  action_overload: {
    title: 'SHOCK',
    desc: 'external intensity shattered the dream',
  },
  lucidity_break: {
    title: 'LUCIDITY_BREAK',
    desc: 'you became too aware',
  },
  dissolution: {
    title: 'DISSOLUTION',
    desc: 'you surrendered completely',
  },
};

export function WakeScreen({ cause, steps, onRestart }: WakeScreenProps) {
  const { title, desc } = causeLabels[cause];

  return (
    <div className="h-screen flex items-center justify-center p-4 relative">
      <div className="starfield" />

      <div className="ascii-box p-6 max-w-sm w-full text-center relative z-10">
        <h1 className="text-gray-400 text-lg tracking-widest mb-6">YOU WAKE</h1>

        <div className="ascii-box p-3 mb-6 border-red-900">
          <div className="text-red-400 text-xs">{title}</div>
          <div className="text-red-300/70 text-xs mt-1">{desc}</div>
        </div>

        <div className="flex justify-center gap-6 text-xs mb-8">
          <div>
            <div className="text-gray-300 text-lg">{steps}</div>
            <div className="text-gray-600">steps</div>
          </div>
        </div>

        <button
          onClick={onRestart}
          className="ascii-btn px-6 py-2 text-sm text-gray-400 hover:text-white"
        >
          [DREAM AGAIN]
        </button>
      </div>
    </div>
  );
}
