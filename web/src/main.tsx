import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { App } from './App';
import { loadConfig } from './auth/firebase';

// The app cannot decide whether it has real accounts until the backend has
// told it, and every screen depends on that answer, so it is settled before
// the first render rather than raced against it.
void loadConfig().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
});
