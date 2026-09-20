# Dreamwalker — Przygotowanie do rozmowy kwalifikacyjnej

## 1. Czym jest projekt w jednym zdaniu

Dreamwalker to narracyjna gra RPG oparta na multi-agentowym systemie LLM, który w czasie rzeczywistym generuje interaktywny sen na podstawie jednej myśli gracza — łącząc tekst, obraz i adaptacyjną muzykę w spójne doświadczenie.

---

## 2. Architektura ogólna — monorepo

```
dreamwalker/
├── client/        React 19 + Vite + TypeScript + Tailwind 4 + Zustand
├── server/        Bun + Express 5 + WebSocket (ws) + TypeScript
└── shared/        Wspólne typy TypeScript (GameState, Step, Metrics, …)
```

Projekt to monorepo z trzema pakietami. `shared/` eksportuje tylko typy — dzięki temu klient i serwer mówią tym samym językiem bez duplikowania definicji. Środowiskiem uruchomieniowym jest **Bun**, który obsługuje zarówno bundling, jak i runtime serwera.

---

## 3. System psychologiczny — metryki

To rdzeń mechaniki gry, projektowany zanim napisano linijkę kodu.

### Metryki bazowe (zakres –100 do +100)

| Metryka         | Co mierzy                                                  |
|-----------------|------------------------------------------------------------|
| `arousal`       | Intensywność akcji: spokój (–) ↔ ekstremalne napięcie (+)  |
| `valence`       | Nastrój emocjonalny: ciemność (–) ↔ jasność (+)            |
| `selfAwareness` | Świadomość śnienia: immersja (–) ↔ lucydność (+)           |

### Metryki pochodne (wyliczane na żądanie)

```ts
luck       = clamp(50 + valence/2 + selfAwareness/2, 0, 100)
turbulence = |arousal| + |valence|
```

### Mechanika driftu

Co krok wszystkie metryki dryfują o 5 punktów w kierunku 0. To kluczowa decyzja projektowa — zapobiega permanentnym stanom ekstremalnym i wymusza naturalną oscylację narracji.

### Warunki przebudzenia

```ts
selfAwareness > 90   → 'lucidity_break'
selfAwareness < -90  → 'dissolution'
|arousal| > 90       → 'action_overload'
|valence| > 90       → 'emotional_overload'
```

---

## 4. Multi-agentowy pipeline — krok po kroku

Każdy „krok" (step) w grze to orkiestracja **pięciu agentów LLM** wykonywanych sekwencyjnie:

```
Krok 1 (tylko raz): Initiator
           ↓
Krok N≥2: Director (pobiera dane z poprzedniego kroku)
           ↓
         Storyteller  ← historia konwersacji (ostatnie 30 wiadomości)
           ↓
         Brancher     ← tekst sceny od Storytellera
           ↓
         Judge        ← tekst + wybory od Branchera
           ↓
     [fire & forget] Image generation
           ↓
     Odpowiedź do klienta: { step, state }
```

### Agenci — szczegóły

#### 🌍 Initiator (jednorazowy)
Tworzy fundament świata snu z jednej myśli gracza.

**Wejście:** `"a dream"` lub myśl gracza (np. *"stary kampus w letni wieczór"*)

**Wyjście (JSON):**
```json
{
  "world": "~100 słów: reguły, fizyka, atmosfera świata",
  "writingStyle": "np. 'terse and clinical'",
  "visualStyle": "np. 'washed-out polaroid nostalgia'",
  "audioStyle": "np. 'distant ambient hum'"
}
```

**Dlaczego osobny agent?** Separacja *inicjalizacji świata* od *narracji* pozwala Storytellerowi skupić się wyłącznie na kontynuacji — nie musi on rozumieć, czym jest ten świat, dostaje go gotowy w system prompt.

#### 📖 Storyteller (każdy krok)
Pisze 2–4 zdania narracji, reagując na ostatni wybór gracza.

**Kluczowe:** jedyny agent z **historią konwersacji** (role: user/assistant). Dzięki temu buduje kontekst stylistyczny i fabularny przez całą sesję. Historia jest przycinana do 30 ostatnich wiadomości, żeby nie eksplodował kontekst.

System prompt zawiera `world`, `writingStyle` oraz guidance Directora.

#### 🌿 Brancher (każdy krok)
Generuje 1–4 krótkie, akcjonowalne wybory (3–8 słów każdy).

**Dlaczego osobny prompt, nie wspólny ze Storytellerem?** Storyteller ma tendencję do pisania wyborów spójnych fabularnie, ale płytkich mechanicznie. Brancher dostaje tylko tekst sceny i historię — patrzy na sytuację „z zewnątrz" i generuje różnorodniejsze opcje.

#### ⚖️ Judge (każdy krok)
Ocenia scenę i każdy wybór na trzech osiach psychologicznych, liczby całkowite w zakresie [–25, +25].

**Wyjście:**
```json
{
  "event": { "arousal": 10, "valence": -5, "selfAwareness": 0 },
  "choices": [
    { "arousal": 15, "valence": 5, "selfAwareness": -3 },
    { "arousal": -10, "valence": 20, "selfAwareness": 8 }
  ]
}
```

Judge nie wie, który wybór gracz wybierze — ocenia każdy niezależnie. Te oceny są przypisywane do decyzji i aplikowane do metryk dopiero gdy gracz kliknie wybór (endpoint `/decide`). Dzięki temu gra ma realny wpływ emocjonalny na mechanikę.

#### 🎬 Director (od kroku 2)
Meta-agent pacing'owy. Widzi: aktualne metryki, historię, output Storytellera, oceny Judga i wybór gracza. Decyduje czy zmienić lokację i przekazuje krótki `guidance` do Storytellera w następnym kroku.

**Dlaczego Director jest PRZED Storytellerem, nie po?** Bo jego guidance musi wpłynąć na *następną* scenę, nie na obecną. Director jest pomostem między krokami — czyta, co właśnie się wydarzyło, i mówi narratorowi, gdzie zmierzać.

---

## 5. Structured Output — kluczowy wzorzec

Każdy agent używa **Gemini JSON mode** z jawnie zdefiniowanym schematem:

```ts
const JUDGE_SCHEMA = {
  type: Type.OBJECT,
  properties: {
    event: METRICS_SCHEMA,
    choices: { type: Type.ARRAY, items: METRICS_SCHEMA }
  },
  required: ['event', 'choices'],
};
```

`responseMimeType: 'application/json'` + `responseSchema` wymusza na modelu zwracanie parsowanego JSON. To eliminuje potrzebę promptowania w stylu *"odpowiedz w JSON"* i sprawia, że integracja jest deterministyczna typowo. Odpowiedź jest bezpośrednio rzutowana na interfejsy TypeScript.

Każde wywołanie logowane jest przez `logAI(label, input, rawText)` — pomocne przy debugowaniu promptów.

---

## 6. Generowanie mediów

### Obrazy — `gemini-2.5-flash-image`

Generowane **asynchronicznie, fire-and-forget** — nie blokują dostarczenia kroku do gracza. Każdy obraz jest keszowany na dysku przez 24h kluczem SHA-256 z promptu:

```ts
const cacheKey = sha256(`${visualStyle}|${locationDescription}|${storyContext}`)
```

Jeśli ten sam prompt wraca (np. ta sama lokacja), obraz nie jest regenerowany. Oszczędność kosztów i latency.

### Muzyka — Lyria realtime (`lyria-realtime-exp`)

Muzyka streamowana **live przez WebSocket** (`ws://…/api/audio?sessionId=…`). Po każdym kroku serwer wywołuje `updateAudioPrompt`, który przelicza soundscape na podstawie aktualnych metryk:

```ts
bpm = 40 + |arousal| * 0.8   // 40–120 BPM
```

Prompt muzyczny jest funkcją arousal, valence, selfAwareness + audioStyle lokacji. Jeśli nowy prompt jest identyczny z poprzednim (np. metryki prawie się nie zmieniły), aktualizacja jest pomijana — ważna optymalizacja dla API.

---

## 7. Infrastruktura serwera

### Sesje
In-memory Map z TTL 1h. Brak bazy danych — celowy wybór dla demo/gry: prostota, zero latency odczytu, naturalne czyszczenie przy restarcie serwera.

### Cache mediów
Pliki na dysku (.png, .mp3) z osobnym schedulem czyszczenia (co 1h).

### REST API
```
POST /api/session              → stwórz sesję
GET  /api/session/:id          → pobierz stan
POST /api/session/:id/generate → wygeneruj krok
POST /api/session/:id/decide   → zastosuj decyzję
GET  /api/session/:id/derived  → metryki pochodne
DELETE /api/session/:id        → usuń sesję
WS   /api/audio?sessionId=…    → stream muzyki
```

### Klient — Zustand store
Stan gry po stronie klienta zarządzany przez Zustand. Jeden centralny store (`useGameStore`) z metodami odpowiadającymi endpointom. Brak React Query, brak skomplikowanego cache — Zustand wystarcza przy prostym modelu: jeden stan gry na sesję.

---

## 8. Tech stack — podsumowanie

| Warstwa       | Technologie                                              |
|---------------|----------------------------------------------------------|
| **Runtime**   | Bun (server + dev bundler)                               |
| **Backend**   | Express 5, ws, TypeScript                                |
| **Frontend**  | React 19, Vite, Tailwind 4, Zustand                      |
| **AI (text)** | Google Gemini `gemini-3.1-flash-lite-preview` via `@google/genai` |
| **AI (img)**  | Google Gemini `gemini-2.5-flash-image`                   |
| **AI (audio)**| Google Lyria `lyria-realtime-exp`                        |
| **Typy**      | TypeScript end-to-end, shared types między client/server |

Model `gemini-3.1-flash-lite-preview` dla agentów tekstowych — celowy wybór: szybki i tani przy structured output. Nie potrzeba Opus/Pro do generowania 2–4 zdań narracji w JSON.

---

## 9. Ewaluacja

### Ewaluacja w pętli (in-loop evaluation)
**Judge** to de facto ewaluator jakości emocjonalnej sceny — ocenia każdą scenę na trzech osiach. Te oceny nie są tylko feedbackiem dla gracza, ale wpływają bezpośrednio na mechanikę gry (metryki, warunki przebudzenia). To przykład **ewaluacji zintegrowanej z systemem**, nie post-hoc.

**Director** to meta-ewaluator pacing'owy — ocenia, czy narracja zmierza w dobrym kierunku strukturalnie.

### Czego brakuje — uczciwa ocena
Projekt nie ma:
- **offline eval setu** — zbioru przykładowych promptów z oczekiwanymi wyjściami
- **metryk jakości agentów** — nie mierzymy np. czy Brancher generuje faktycznie różnorodne wybory
- **A/B testów promptów** — prompty są dobrane intuicyjnie, nie empirycznie
- **automatycznych testów regresji** dla pipeline'u agentów

---

## 10. Co można by usprawnić

### Techniczne

**1. Równoległość agentów**
Brancher i Judge mogłyby działać współbieżnie — Judge potrzebuje tekstu sceny, nie czeka na wybory Branchera. Aktualnie są sekwencyjne. Potencjalnie ~30% skrócenie czasu generowania kroku.

**2. Streaming tekstu do klienta**
Storyteller generuje cały tekst zanim trafi do klienta. Można by streamować przez SSE/WebSocket, żeby gracz widział narrację pisaną literka po literka — dramatycznie lepszy UX.

**3. Retry logic dla agentów**
Brak mechanizmu retry przy błędzie API. Przy `gemini-3.1-flash-lite-preview` czasem zdarzają się timeout'y, szczególnie przy równoległych sesjach.

**4. Kompresja historii konwersacji**
Storyteller tnie historię do 30 ostatnich wiadomości, ale nie robi jej kompresji/streszczenia. W głębokiej sesji (~80 kroków) traci się kontekst z początku snu. Można by dodać periodic summarization — agent streszcza pierwsze N wiadomości w jedno podsumowanie.

**5. Persystencja sesji**
In-memory store traci wszystkie sesje przy restarcie serwera. Redis lub SQLite rozwiązałyby problem bez dużego overhead'u.

### Architektoniczne

**6. Formalna ewaluacja agentów**
Zbudowanie eval setu: 20–30 sytuacji fabularnych z oczekiwanym zakresem metryk od Judge'a, oczekiwaną liczbą wyborów od Branchera. Pozwoliłoby na empiryczne porównanie wersji promptów.

**7. Fine-tuning Judge'a**
Judge ocenia emocje na podstawie zero-shot prompting — spójność ocen między sesjami jest niezagwarantowana. Fine-tuned model (lub few-shot z przykładami) dałby bardziej deterministyczne oceny.

**8. Multiplayer**
Game plan wspomina o multiplayer — techniczny fundament (sesje, WebSocket dla audio) już jest. Następny krok to shared dream state z merge'owaniem decyzji wielu graczy.

---

## 11. Przykładowy opis na rozmowę

> Dreamwalker to projekt, który zrobiłem z ciekawości — chciałem zobaczyć, czy da się zbudować spójne, interaktywne doświadczenie narracyjne w pełni generowane przez LLM. Gra polega na tym, że piszesz jedną myśl, a system buduje z niej interaktywny sen z własną fizyką i estetyką.
>
> Technicznie to multi-agentowy pipeline na Gemini. Zaprojektowałem pięć agentów z rozdzielonymi odpowiedzialnościami: **Initiator** tworzy świat na starcie, **Storyteller** pisze narrację krok po kroku z historią konwersacji, **Brancher** generuje wybory, **Judge** ocenia emocjonalny ciężar każdej sceny na trzech osiach psychologicznych — arousal, valence i selfAwareness — a **Director** reguluje tempo narracji między krokami, przekazując guidance Storytellerowi.
>
> Kluczowe decyzje projektowe: po pierwsze, **structured output** — każdy agent zwraca JSON ze ściśle zdefiniowanym schematem, co sprawia, że integracja jest deterministyczna i typebezpieczna end-to-end w TypeScript. Po drugie, **metryki psychologiczne** są prawdziwą mechaniką gry, a nie tylko wizualizacją — jeśli emocje gracza skrajnie rosną przez kilka kroków, sen się kończy. Judge jest w tym sensie ewaluatorem wbudowanym w system. Po trzecie, obrazy generowane są fire-and-forget asynchronicznie z SHA-256 keszem, żeby nie blokować odpowiedzi do gracza, a muzyka płynie live przez WebSocket z Google Lyria, dynamicznie zmieniając się z każdym krokiem.
>
> Co bym poprawił? Przede wszystkim równoległość — Brancher i Judge mogą działać jednocześnie, bo Judge nie potrzebuje wyborów do oceny sceny. Dodałbym też streaming tekstu SSE do klienta i formalny eval set dla agentów — teraz prompty dobierane są intuicyjnie, a chciałbym móc empirycznie porównywać ich wersje. No i kompresja historii konwersacji przy długich sesjach — obecnie po prostu ucinamy, co prowadzi do utraty kontekstu z początku snu.
>
> Projekt nauczył mnie, jak projektować orkiestrację agentów tak, żeby każdy miał jedno, dobrze zdefiniowane zadanie — zamiast jednego dużego prompta, który robi wszystko. To bezpośrednio przekłada się na debugowalność i możliwość niezależnego ulepszania każdego agenta.

---

## 12. Potencjalne pytania techniczne i odpowiedzi

**Q: Dlaczego nie użyłeś LangChain/LangGraph?**

Projekt budowałem customowo, bo zależało mi na pełnej kontroli nad przepływem — pipeline ma specyficzną sekwencję z warunkowym uruchomieniem agentów (Director tylko od kroku 2, Initiator tylko raz). LangChain dodałby overhead abstrakcji bez realnego zysku przy tak małej liczbie agentów. Przy skali i potrzebie reusability warto byłoby rozważyć.

**Q: Jak radzisz sobie z halucynacjami agentów?**

Structured output z `responseSchema` bardzo ogranicza problem — model nie może zwrócić nieprawidłowej struktury. Dla wartości liczbowych (metryki Judge'a) zakres [–25, +25] jest wyegzekwowany przez prompt, ale nie przez schemat — to potencjalna podatność. Dodałbym walidację zakresów po stronie serwera.

**Q: Jak skalowalny jest ten system?**

Aktualnie in-memory, single-instance — celowo, to projekt demo. Przy skalowaniu: Redis dla sesji, queue (np. BullMQ) dla requestów do Gemini żeby respektować rate limits API, oraz edge caching dla mediów.

**Q: Co mierzy Judge dokładnie?**

Judge patrzy na tekst sceny i wybory, nie na metryki sesji. Ocenia *emocjonalny ładunek* konkretnego momentu narracji, nie jego konsekwencje w kontekście całej sesji. To intencjonalne — chcemy, żeby Judge był obiektywnym krytykiem sceny, nie strażnikiem stanu gry.
