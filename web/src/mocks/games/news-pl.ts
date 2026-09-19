import type { MockGame } from '../types';
import { mapNews, startPos } from '../maps';
import { placeholderImage } from '../placeholder';

const map = mapNews(['Punkt zbiórki', 'Wał przeciwpowodziowy', 'Szkoła', 'Most', 'Świetlica']);

/** Safe-mode fixture: a disaster, played as a volunteer, with a content note. */
export const newsPl: MockGame = {
  id: 'mock-news-pl',
  request: { mode: 'news', region: 'pl', story_language: 'pl', ui_language: 'pl' },
  state: {
    game_id: 'mock-news-pl',
    mode: 'news',
    view: 'scene',
    region: 'pl',
    story_language: 'pl',
    ui_language: 'pl',
    safety_class: 'safe_mode',
    content_note:
      'Ta historia opiera się na prawdziwej powodzi i jej skutkach dla mieszkańców. ' +
      'Grasz jako wolontariusz. Nie ma tu drastycznych opisów, a osoby prywatne ' +
      'pozostają anonimowe. Jeśli temat jest dla Ciebie trudny, możesz wrócić do menu.',
    source_note: 'na podstawie prawdziwych wydarzeń, zdramatyzowane',
    style_card: {
      genre: 'documentary',
      narrative_voice: 'second_present',
      tone: 'reverent',
      protagonist_role: 'volunteer',
      visual_style: 'ink_wash',
      music_mood: 'elegy',
      pacing: 'slow_burn',
    },
    map,
    player_pos: startPos(map),
    visited: [],
    resolved: [],
    unlocked: [],
    current_scene: {
      id: 'sc-start',
      location_id: 'start',
      text:
        'Syrena poszła o czwartej trzydzieści i od tamtej pory nikt w tej wsi nie wrócił do łóżka. ' +
        'Przyjechałeś z workami i łopatą, bo tak zrobiła połowa powiatu. Ktoś rozdaje kamizelki przy ' +
        '[LOC:punkcie zbiórki]. Woda jest jeszcze pół metra pod koroną wału.',
      image_url: placeholderImage('start-pl', 'moss'),
    },
    choices: [],
    beat_progress: [
      { beat_id: 'b1', status: 'pending' },
      { beat_id: 'b2', status: 'pending' },
      { beat_id: 'b3', status: 'pending' },
      { beat_id: 'b4', status: 'pending' },
      { beat_id: 'b5', status: 'pending' },
    ],
    divergence: 0,
    turn: 0,
    finished: false,
  },
  scenes: {
    'loc-a': {
      id: 'sc-a',
      location_id: 'loc-a',
      text:
        'W [LOC:punkcie zbiórki] pachnie kawą z termosu i mokrą wełną. Strażak z ochotniczej straży ' +
        'dzieli ludzi na dwie grupy: tych, którzy pójdą na wał, i tych, którzy zostaną przy ' +
        'rozwożeniu. Nikt nie pyta, kto się do czego nadaje. [KEY:Pytają tylko, kto ma buty.]',
      image_url: placeholderImage('pl-a', 'ash'),
      image_credit: { source_url: 'https://example.org/press/zbiorka', credit: 'PAP / zdjęcie archiwalne' },
    },
    'loc-b': {
      id: 'sc-b',
      location_id: 'loc-b',
      text:
        'Na [LOC:wale] pracuje się w rytmie, którego nikt nie ustalał: worek, podanie, worek, podanie. ' +
        'Obok ciebie stoi kobieta, która nie powiedziała, jak ma na imię, i nie przestała ani na ' +
        'moment. Rzeka nie wygląda na wściekłą. Wygląda na cierpliwą, co jest gorsze.',
      image_url: placeholderImage('pl-b', 'cold'),
    },
    'loc-c': {
      id: 'sc-c',
      location_id: 'loc-c',
      text:
        'W [LOC:szkole] na parterze rozłożono materace między ławkami. Ktoś przykleił taśmą kartkę ' +
        '„TU PYTAĆ O ZWIERZĘTA”. Starszy pan siedzi z psem na kolanach i nie chce iść na górę, ' +
        'dopóki nie dowie się, czy sąsiadka też wyszła.',
      image_url: placeholderImage('pl-c', 'dusk'),
      image_credit: { source_url: 'https://example.org/press/szkola', credit: 'Reuters / zdjęcie archiwalne' },
    },
    'loc-d': {
      id: 'sc-d',
      location_id: 'loc-d',
      text:
        'Na [POI:moście] stoi radiowóz w poprzek jezdni i to wystarcza za wyjaśnienie. Woda idzie ' +
        'pod przęsłem szybciej, niż powinna, i niesie rzeczy, które jeszcze wczoraj stały w czyimś ' +
        'ogrodzie. Most jest zamknięty. Po drugiej stronie też ktoś czeka.',
      image_url: placeholderImage('pl-d', 'rust'),
    },
    'loc-e': {
      id: 'sc-e',
      location_id: 'loc-e',
      text:
        'W [LOC:świetlicy] ktoś rozstawił stoły i postawił na nich wszystko, co przywieźli ludzie ' +
        'z sąsiednich wsi: koce, wodę, karmę, dwie paczki pieluch. Nikt tego nie koordynuje. ' +
        'Działa i tak. Na drzwiach wisi kartka: [KEY:„nie pytamy, czyje. bierzemy, co trzeba”.]',
      image_url: placeholderImage('pl-e', 'moss'),
      image_credit: { source_url: 'https://example.org/press/swietlica', credit: 'PAP / zdjęcie archiwalne' },
    },
  },
  choices: {
    'loc-a': [
      { id: 'a1', text: 'Zgłosić się na wał' },
      { id: 'a2', text: 'Zostać przy rozwożeniu' },
      { id: 'a3', text: 'Spytać, czego brakuje najbardziej' },
    ],
    'loc-b': [
      { id: 'b1', text: 'Pracować dalej bez przerwy' },
      { id: 'b2', text: 'Zmusić sąsiadkę do odpoczynku' },
      { id: 'b3', text: 'Zawołać, że worki się kończą' },
    ],
    'loc-c': [
      { id: 'c1', text: 'Poszukać sąsiadki na liście' },
      { id: 'c2', text: 'Zostać z panem i psem' },
      { id: 'c3', text: 'Zorganizować kąt dla zwierząt' },
    ],
    'loc-d': [
      { id: 'd1', text: 'Uszanować zamknięcie i wrócić' },
      { id: 'd2', text: 'Szukać objazdu dla dostaw' },
      { id: 'd3', text: 'Zostać i pomagać przy zawracaniu aut' },
    ],
    'loc-e': [
      { id: 'e1', text: 'Spisać, czego brakuje' },
      { id: 'e2', text: 'Rozwozić dalej bez liczenia' },
      { id: 'e3', text: 'Usiąść na dziesięć minut' },
    ],
  },
  openQuestionAt: 'loc-c',
  ending: {
    game_id: 'mock-news-pl',
    mode: 'news',
    match_score: 0.81,
    title: 'Powódź w powiecie — wał utrzymany',
    summary:
      'Poszedłeś na wał i zostałeś tam dłużej, niż planowałeś. Potem w szkole zrobiłeś miejsce dla ' +
      'zwierząt, o które nikt oficjalnie nie pytał. Wał wytrzymał. Most otwarto trzy dni później.',
    canon: [
      { id: 'b1', title: 'Alarm powodziowy i ewakuacja', summary: 'Nad ranem ogłoszono alarm; mieszkańców zaczęto wyprowadzać z najniżej położonych domów.', sources: ['https://example.org/pl-a'] },
      { id: 'b2', title: 'Wzmacnianie wału', summary: 'Ochotnicy i straż układali worki z piaskiem przez kilkanaście godzin.', sources: ['https://example.org/pl-a', 'https://example.org/pl-b'] },
      { id: 'b3', title: 'Punkt w szkole', summary: 'W szkole uruchomiono punkt dla ewakuowanych, w tym miejsce dla zwierząt.', sources: ['https://example.org/pl-b'] },
      { id: 'b4', title: 'Most zamknięty', summary: 'Przeprawę zamknięto do czasu opadnięcia wody.', sources: ['https://example.org/pl-c'] },
      { id: 'b5', title: 'Zbiórka darów', summary: 'W świetlicy zorganizowano punkt wydawania darów od mieszkańców okolicznych wsi.', sources: ['https://example.org/pl-b'] },
    ],
    player: [
      { beat_id: 'b1', status: 'matched', what_you_did: 'Zgłosiłeś się od razu i spytałeś, czego brakuje.' },
      { beat_id: 'b2', status: 'matched', what_you_did: 'Pracowałeś na wale i zgłosiłeś brak worków.' },
      { beat_id: 'b3', status: 'matched', what_you_did: 'Zorganizowałeś kąt dla zwierząt w szkole.' },
      { beat_id: 'b4', status: 'diverged', what_you_did: 'Zamiast wracać, szukałeś objazdu dla dostaw.' },
      { beat_id: 'b5', status: 'matched', what_you_did: 'Spisałeś, czego brakuje w świetlicy.' },
    ],
    style_card: {
      genre: 'documentary',
      narrative_voice: 'second_present',
      tone: 'reverent',
      protagonist_role: 'volunteer',
      visual_style: 'ink_wash',
      music_mood: 'elegy',
      pacing: 'slow_burn',
    },
    sources: [
      { url: 'https://example.org/pl-a', title: 'Alarm powodziowy w powiecie' },
      { url: 'https://example.org/pl-b', title: 'Ochotnicy umacniali wał całą noc' },
      { url: 'https://example.org/pl-c', title: 'Most zamknięty do odwołania' },
    ],
  },
  replay: {
    game_id: 'mock-news-pl',
    title: 'Powódź w powiecie — wał utrzymany',
    turns: [
      { turn: 1, scene: { id: 'sc-a', location_id: 'loc-a', text: 'W punkcie zbiórki pachnie kawą z termosu i mokrą wełną.', image_url: placeholderImage('pl-a', 'ash') }, player_pos: { x: 11, y: 1 }, chosen: 'Spytać, czego brakuje najbardziej' },
      { turn: 2, scene: { id: 'sc-b', location_id: 'loc-b', text: 'Na wale pracuje się w rytmie, którego nikt nie ustalał.', image_url: placeholderImage('pl-b', 'cold') }, player_pos: { x: 3, y: 3 }, chosen: 'Zawołać, że worki się kończą' },
      { turn: 3, scene: { id: 'sc-c', location_id: 'loc-c', text: 'W szkole na parterze rozłożono materace między ławkami.', image_url: placeholderImage('pl-c', 'dusk') }, player_pos: { x: 11, y: 5 }, chosen: 'Zorganizować kąt dla zwierząt', answer: 'Że wróci. Że sąsiadka wyszła pierwsza i czeka po drugiej stronie, i że pies może zostać na kolanach.' },
      { turn: 4, scene: { id: 'sc-d', location_id: 'loc-d', text: 'Na moście stoi radiowóz w poprzek jezdni.', image_url: placeholderImage('pl-d', 'rust') }, player_pos: { x: 1, y: 7 }, chosen: 'Szukać objazdu dla dostaw' },
    ],
  },
};
