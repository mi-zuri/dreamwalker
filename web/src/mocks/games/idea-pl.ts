import type { MockGame } from '../types';
import { mapIdea, startPos } from '../maps';
import { placeholderImage } from '../placeholder';

const map = mapIdea(['Przedni wagon', 'Zajezdnia', 'Przystanek Zapomniany', 'Kabina motorniczego']);

export const ideaPl: MockGame = {
  id: 'mock-idea-pl',
  request: {
    mode: 'idea',
    idea: 'nocny tramwaj, który nigdy nie dojeżdża do pętli',
    story_language: 'pl',
    ui_language: 'pl',
  },
  state: {
    game_id: 'mock-idea-pl',
    mode: 'idea',
    story_language: 'pl',
    ui_language: 'pl',
    safety_class: 'allowed',
    style_card: {
      genre: 'absurdist',
      narrative_voice: 'first_past',
      tone: 'deadpan',
      protagonist_role: 'participant',
      visual_style: 'pixel',
      music_mood: 'static',
      pacing: 'staccato',
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
        'Wsiadłem o 23:40 i to była, jak się później okazało, ostatnia informacja, której byłem ' +
        'pewien. Tramwaj jedzie. Wyświetlacz pokazuje [KEY:PĘTLA], konsekwentnie, od czterdziestu ' +
        'minut. Za oknem mija nas ten sam kiosk po raz trzeci i nikt poza mną tego nie komentuje.',
      image_url: placeholderImage('start-idea-pl', 'dusk'),
    },
    choices: [],
    beat_progress: [
      { beat_id: 'b1', status: 'pending' },
      { beat_id: 'b2', status: 'pending' },
      { beat_id: 'b3', status: 'pending' },
      { beat_id: 'b4', status: 'pending' },
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
        'W [LOC:przednim wagonie] siedzi sześć osób i każda z nich ma bilet skasowany o 23:40. ' +
        'Sprawdziłem. Grzecznie, ale sprawdziłem. Kobieta przy oknie powiedziała, że jedzie do ' +
        'pracy, po czym dodała, że nie pamięta, gdzie pracuje, i uznała to za śmieszne.',
      image_url: placeholderImage('idea-pl-a', 'cold'),
    },
    'loc-b': {
      id: 'sc-b',
      location_id: 'loc-b',
      text:
        '[LOC:Zajezdnia] istnieje. To już coś. Brama jest otwarta, w środku stoją cztery tramwaje ' +
        'tej samej linii i wszystkie mają zapalone światła. Na tablicy dyspozytora widnieje jeden ' +
        'wpis, powtórzony czterdzieści razy: [POI:wyjazd 23:40].',
      image_url: placeholderImage('idea-pl-b', 'ash'),
    },
    'loc-c': {
      id: 'sc-c',
      location_id: 'loc-c',
      text:
        'Na [LOC:Przystanku Zapomnianym] rozkład jazdy jest pusty. Nie zniszczony — wydrukowany ' +
        'pusty, z nagłówkiem i liniami, i niczym pomiędzy. Ktoś dopisał długopisem godzinę. ' +
        'Oczywiście 23:40. Ktoś inny to przekreślił i napisał obok: „nie wsiadaj”.',
      image_url: placeholderImage('idea-pl-c', 'rust'),
    },
    'loc-d': {
      id: 'sc-d',
      location_id: 'loc-d',
      text:
        'W [LOC:kabinie motorniczego] nie ma motorniczego. Jest kurtka na oparciu, ciepła kawa i ' +
        'notes, w którym ktoś prowadzi rachunek kółek. Ostatnia liczba to 6141. Przed chwilą, ' +
        'kiedy patrzyłem, było 6140.',
      image_url: placeholderImage('idea-pl-d', 'moss'),
    },
  },
  choices: {
    'loc-a': [
      { id: 'a1', text: 'Spytać, kto wsiadł jako pierwszy' },
      { id: 'a2', text: 'Pociągnąć hamulec bezpieczeństwa' },
      { id: 'a3', text: 'Usiąść i policzyć kioski' },
    ],
    'loc-b': [
      { id: 'b1', text: 'Wejść do drugiego tramwaju' },
      { id: 'b2', text: 'Zetrzeć wpis z tablicy' },
      { id: 'b3', text: 'Zamknąć bramę zajezdni' },
    ],
    'loc-c': [
      { id: 'c1', text: 'Dopisać własną godzinę' },
      { id: 'c2', text: 'Zostać na przystanku' },
      { id: 'c3', text: 'Zabrać rozkład ze sobą' },
    ],
    'loc-d': [
      { id: 'd1', text: 'Dopisać 6142 i wysiąść' },
      { id: 'd2', text: 'Włożyć kurtkę' },
      { id: 'd3', text: 'Wyrwać stronę z notesu' },
    ],
  },
  openQuestionAt: 'loc-c',
  ending: {
    game_id: 'mock-idea-pl',
    mode: 'idea',
    title: 'Kółko 6142',
    summary:
      'Nie pociągnąłem hamulca, chociaż mogłem, i to prawdopodobnie była właściwa decyzja. ' +
      'Dopisałem własną godzinę na pustym rozkładzie, a potem, w kabinie, dopisałem 6142 i ' +
      'wysiadłem na przystanku, którego nie było w rozkładzie, bo rozkład miałem w kieszeni.',
    canon: [],
    player: [
      { beat_id: 'b1', status: 'matched', what_you_did: 'Spytałeś, kto wsiadł jako pierwszy.' },
      { beat_id: 'b2', status: 'diverged', what_you_did: 'Zamknąłeś bramę zajezdni.' },
      { beat_id: 'b3', status: 'matched', what_you_did: 'Dopisałeś własną godzinę i zabrałeś rozkład.' },
      { beat_id: 'b4', status: 'matched', what_you_did: 'Dopisałeś 6142 i wysiadłeś.' },
    ],
    style_card: {
      genre: 'absurdist',
      narrative_voice: 'first_past',
      tone: 'deadpan',
      protagonist_role: 'participant',
      visual_style: 'pixel',
      music_mood: 'static',
      pacing: 'staccato',
    },
    sources: [],
  },
  replay: {
    game_id: 'mock-idea-pl',
    title: 'Kółko 6142',
    turns: [
      { turn: 1, scene: { id: 'sc-a', location_id: 'loc-a', text: 'W przednim wagonie siedzi sześć osób.', image_url: placeholderImage('idea-pl-a', 'cold') }, player_pos: { x: 8, y: 1 }, chosen: 'Spytać, kto wsiadł jako pierwszy' },
      { turn: 2, scene: { id: 'sc-b', location_id: 'loc-b', text: 'Zajezdnia istnieje. To już coś.', image_url: placeholderImage('idea-pl-b', 'ash') }, player_pos: { x: 1, y: 5 }, chosen: 'Zamknąć bramę zajezdni' },
      { turn: 3, scene: { id: 'sc-c', location_id: 'loc-c', text: 'Na Przystanku Zapomnianym rozkład jazdy jest pusty.', image_url: placeholderImage('idea-pl-c', 'rust') }, player_pos: { x: 12, y: 6 }, chosen: 'Zabrać rozkład ze sobą', answer: '23:41. Celowo. Żeby był chociaż jeden kurs, którego ten tramwaj nie zna.' },
      { turn: 4, scene: { id: 'sc-d', location_id: 'loc-d', text: 'W kabinie motorniczego nie ma motorniczego.', image_url: placeholderImage('idea-pl-d', 'moss') }, player_pos: { x: 6, y: 7 }, chosen: 'Dopisać 6142 i wysiąść' },
    ],
  },
};
