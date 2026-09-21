import { useStore } from '../../store';
import { t } from '../../i18n';
import { Starfield } from '../Starfield';
import { Header } from '../Header';
import type { NewsStory } from '../../types';

const FRESHNESS = {
  fresh: 'freshnessFresh',
  aging: 'freshnessAging',
  stale: 'freshnessStale',
} as const;

/**
 * The stories on offer, most important first.
 *
 * Which story to play used to be the server's choice, weighted-random over
 * the top of the pool. It is the player's now, so the pool has to be visible
 * before they choose - which is also why the wait for a cold pool happens
 * here rather than behind the loading screen of a game already under way.
 */
export function StoryPicker() {
  const { language, stories, busy, start, toMenu } = useStore();

  return (
    <div className="h-screen flex flex-col p-3 overflow-hidden relative">
      <Starfield />
      <Header
        language={language}
        right={
          <button onClick={toMenu} className="hover:text-gray-300">
            {t(language, 'storiesBack')}
          </button>
        }
      />

      <div className="flex-1 flex items-center justify-center relative z-10 min-h-0">
        <div className="ascii-box p-5 max-w-2xl w-full flex flex-col min-h-0">
          <div className="text-indigo-400 text-sm tracking-widest mb-1">
            {t(language, 'storiesTitle')}
          </div>
          <div className="text-xs text-gray-600 mb-4">{t(language, 'storiesHint')}</div>

          {busy ? (
            <div className="text-xs text-gray-600 py-8 text-center">
              {t(language, 'storiesLoading')}
            </div>
          ) : stories.length === 0 ? (
            <div className="text-xs text-gray-500 py-8 text-center">
              {t(language, 'storiesEmpty')}
            </div>
          ) : (
            <div className="overflow-y-auto min-h-0 space-y-2">
              {stories.map((story: NewsStory, i: number) => (
                <button
                  key={story.id}
                  onClick={() => start(story.id)}
                  className="ascii-btn w-full p-2 text-left"
                >
                  <div className="flex items-baseline gap-2">
                    <span className="text-indigo-400 text-sm">[{i + 1}]</span>
                    {/* Two lines at most: seven rows have to fit one screen. */}
                    <span className="text-gray-200 text-sm line-clamp-2">{story.title}</span>
                  </div>
                  <div className="text-[10px] text-gray-600 mt-1 ml-7">
                    {t(language, FRESHNESS[story.freshness])}
                    {story.safety_class === 'safe_mode' && (
                      <span className="text-pink-400"> · {t(language, 'storyNote')}</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
