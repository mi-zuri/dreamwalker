import { useEffect } from 'react';
import { useStore } from './store';
import { LoginScreen } from './components/screens/LoginScreen';
import { MainMenu } from './components/screens/MainMenu';
import { ContentNote } from './components/screens/ContentNote';
import { LoadingScreen } from './components/screens/LoadingScreen';
import { GameScreen } from './components/screens/GameScreen';
import { EndingScreen } from './components/screens/EndingScreen';
import { LibraryScreen } from './components/screens/LibraryScreen';
import { ReplayScreen } from './components/screens/ReplayScreen';
import { ErrorScreen } from './components/screens/ErrorScreen';
import { DevPanel } from './components/DevPanel';
import { Starfield } from './components/Starfield';

const SCREENS = {
  login: LoginScreen,
  menu: MainMenu,
  contentNote: ContentNote,
  loading: LoadingScreen,
  game: GameScreen,
  ending: EndingScreen,
  library: LibraryScreen,
  replay: ReplayScreen,
  error: ErrorScreen,
} as const;

export function App() {
  const screen = useStore((s) => s.screen);
  const restoring = useStore((s) => s.restoring);
  const restoreSession = useStore((s) => s.restoreSession);

  // A persisted Firebase session should survive a refresh without a round trip
  // through the login screen.
  useEffect(() => {
    void restoreSession();
  }, [restoreSession]);

  if (restoring) {
    return (
      <div className="h-screen flex items-center justify-center relative">
        <Starfield />
        <div className="text-xs text-gray-600 relative z-10">z</div>
      </div>
    );
  }

  const Screen = SCREENS[screen];
  return (
    <>
      <Screen />
      <DevPanel />
    </>
  );
}
