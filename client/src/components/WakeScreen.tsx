import type { WakeCause } from '../../../shared/types';

interface WakeScreenProps {
  cause: WakeCause;
  depth: number;
  steps: number;
  onRestart: () => void;
}

const causeLabels: Record<WakeCause, { title: string; description: string }> = {
  emotional_overload: {
    title: 'Emotional Overload',
    description: 'The feelings became too intense to contain.',
  },
  action_overload: {
    title: 'Shock',
    description: 'The external intensity shattered the dream.',
  },
  lucidity_break: {
    title: 'Lucidity Break',
    description: 'You became too aware. The dream could not hold.',
  },
  dissolution: {
    title: 'Dissolution',
    description: 'You surrendered too completely. You lost yourself.',
  },
  terror_spiral: {
    title: 'Terror Spiral',
    description: 'Fear consumed everything.',
  },
  stagnation: {
    title: 'Stagnation',
    description: 'The stillness became absolute. Nothing remained.',
  },
  turbulence_critical: {
    title: 'Reality Fracture',
    description: 'The dream tore itself apart.',
  },
};

export function WakeScreen({ cause, depth, steps, onRestart }: WakeScreenProps) {
  const { title, description } = causeLabels[cause];

  return (
    <div className="fixed inset-0 bg-black/95 flex items-center justify-center">
      <div className="text-center max-w-md px-6">
        <h1 className="text-4xl font-light text-white mb-4">You Wake</h1>

        <div className="bg-red-900/30 border border-red-800/50 rounded-lg px-4 py-2 mb-8">
          <p className="text-red-400 font-medium">{title}</p>
          <p className="text-red-300/70 text-sm mt-1">{description}</p>
        </div>

        <div className="flex justify-center gap-8 text-sm text-gray-400 mb-12">
          <div>
            <span className="block text-2xl text-white">{depth}</span>
            Depth Reached
          </div>
          <div>
            <span className="block text-2xl text-white">{steps}</span>
            Steps Survived
          </div>
        </div>

        <button
          onClick={onRestart}
          className="px-8 py-3 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors"
        >
          Dream Again
        </button>
      </div>
    </div>
  );
}
