import type { MockGame } from '../types';
import { mapNews, startPos } from '../maps';
import { placeholderImage } from '../placeholder';

const map = mapNews(['Launch Control', 'Tower Base', 'Press Pen', 'Recovery Bay']);

export const newsWorldEn: MockGame = {
  id: 'mock-news-world-en',
  request: { mode: 'news', region: 'world', story_language: 'en', ui_language: 'en' },
  state: {
    game_id: 'mock-news-world-en',
    mode: 'news',
    region: 'world',
    story_language: 'en',
    ui_language: 'en',
    safety_class: 'allowed',
    source_note: 'based on real events, dramatized',
    style_card: {
      genre: 'procedural',
      narrative_voice: 'second_present',
      tone: 'dry',
      protagonist_role: 'participant',
      visual_style: 'grainy_photo',
      music_mood: 'pulse',
      pacing: 'escalating',
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
        'Nine minutes to launch and the wind is doing something the forecast did not promise. ' +
        'You are the pad recovery tech, which today means you are the person who walks toward the ' +
        'thing everyone else walks away from. Your radio is already busy. [LOC:Launch Control] wants ' +
        'eyes on the tower.',
      image_url: placeholderImage('start-world', 'ash'),
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
        'Inside [LOC:Launch Control] nobody is shouting, which is how you know it is going badly. ' +
        'The flight director is reading a number off a screen twice. On the wall, the booster sits ' +
        'lit from below like a monument that has not decided yet what it commemorates. ' +
        '[KEY:T-minus four minutes.]',
      image_url: placeholderImage('world-a', 'cold'),
      image_credit: { source_url: 'https://example.org/press/launch-control', credit: 'Press pool / file photo' },
    },
    'loc-b': {
      id: 'sc-b',
      location_id: 'loc-b',
      text:
        'At [LOC:Tower Base] the sound arrives before the light does, through the concrete, up ' +
        'through your boots. The booster is coming back down. The arms of the tower open like ' +
        'someone preparing to catch a falling child, which is exactly what this is, at scale.',
      image_url: placeholderImage('world-b', 'rust'),
    },
    'loc-c': {
      id: 'sc-c',
      location_id: 'loc-c',
      text:
        'The [POI:press pen] is a line of tripods and cold coffee. A reporter asks you, on record, ' +
        'whether it is safe. You have a company answer and a real answer and about two seconds to ' +
        'decide which one this person deserves.',
      image_url: placeholderImage('world-c', 'ash'),
      image_credit: { source_url: 'https://example.org/press/press-pen', credit: 'Reuters / file photo' },
    },
    'loc-d': {
      id: 'sc-d',
      location_id: 'loc-d',
      text:
        'In the [LOC:Recovery Bay] the booster is horizontal and ticking as it cools. It is the ' +
        'least dramatic it will ever look and the most dangerous it has been all day. Someone has ' +
        'to sign the sheet that says the vehicle is safed. The pen is in your hand.',
      image_url: placeholderImage('world-d', 'moss'),
    },
  },
  choices: {
    'loc-a': [
      { id: 'a1', text: 'Call the wind violation out loud' },
      { id: 'a2', text: 'Let the flight director get there first' },
      { id: 'a3', text: 'Ask for the pad camera feed' },
    ],
    'loc-b': [
      { id: 'b1', text: 'Hold position and watch the catch' },
      { id: 'b2', text: 'Fall back behind the blast berm' },
      { id: 'b3', text: 'Radio the arm alignment you can see' },
    ],
    'loc-c': [
      { id: 'c1', text: 'Give the reporter the real answer' },
      { id: 'c2', text: 'Give the company answer' },
      { id: 'c3', text: 'Say nothing and point at the press officer' },
    ],
    'loc-d': [
      { id: 'd1', text: 'Sign it' },
      { id: 'd2', text: 'Walk the vehicle one more time first' },
      { id: 'd3', text: 'Refuse until the vent cycle completes' },
    ],
  },
  openQuestionAt: 'loc-c',
  ending: {
    game_id: 'mock-news-world-en',
    mode: 'news',
    match_score: 0.72,
    title: 'Booster caught, third attempt',
    summary:
      'You stayed at the tower for the catch and told a reporter the truth before the press office ' +
      'had agreed on one. The vehicle came home. Your name is on the safing sheet, thirty seconds ' +
      'later than it should have been, because you walked it one more time.',
    canon: [
      { id: 'b1', title: 'Launch on the second window', summary: 'Winds held inside limits and the vehicle flew at the reopened window.', sources: ['https://example.org/a'] },
      { id: 'b2', title: 'Boostback burn nominal', summary: 'The booster turned and burned back toward the pad on schedule.', sources: ['https://example.org/b'] },
      { id: 'b3', title: 'Tower catch succeeds', summary: 'The arms took the booster cleanly on the third attempt in the programme.', sources: ['https://example.org/b', 'https://example.org/c'] },
      { id: 'b4', title: 'Vehicle safed after extended vent', summary: 'Safing ran long; residual pressure delayed the sign-off.', sources: ['https://example.org/c'] },
    ],
    player: [
      { beat_id: 'b1', status: 'matched', what_you_did: 'You flagged the wind and deferred to the flight director.' },
      { beat_id: 'b2', status: 'matched', what_you_did: 'You called the arm alignment from the tower base.' },
      { beat_id: 'b3', status: 'matched', what_you_did: 'You held position and watched it come down.' },
      { beat_id: 'b4', status: 'diverged', what_you_did: 'You refused to sign until the vent cycle finished.' },
    ],
    style_card: {
      genre: 'procedural',
      narrative_voice: 'second_present',
      tone: 'dry',
      protagonist_role: 'participant',
      visual_style: 'grainy_photo',
      music_mood: 'pulse',
      pacing: 'escalating',
    },
    sources: [
      { url: 'https://example.org/a', title: 'Launch window reopens after wind hold' },
      { url: 'https://example.org/b', title: 'Booster returns to launch site' },
      { url: 'https://example.org/c', title: 'Third successful tower catch' },
    ],
  },
  replay: {
    game_id: 'mock-news-world-en',
    title: 'Booster caught, third attempt',
    turns: [
      { turn: 1, scene: { id: 'sc-a', location_id: 'loc-a', text: 'Inside Launch Control nobody is shouting.', image_url: placeholderImage('world-a', 'cold') }, player_pos: { x: 11, y: 1 }, chosen: 'Let the flight director get there first' },
      { turn: 2, scene: { id: 'sc-b', location_id: 'loc-b', text: 'At Tower Base the sound arrives before the light does.', image_url: placeholderImage('world-b', 'rust') }, player_pos: { x: 3, y: 3 }, chosen: 'Radio the arm alignment you can see' },
      { turn: 3, scene: { id: 'sc-c', location_id: 'loc-c', text: 'The press pen is a line of tripods and cold coffee.', image_url: placeholderImage('world-c', 'ash') }, player_pos: { x: 11, y: 5 }, chosen: 'Give the reporter the real answer', answer: 'That it is safe the way a bridge is safe. Built to hold, tested to hold, and still a bridge.' },
      { turn: 4, scene: { id: 'sc-d', location_id: 'loc-d', text: 'In the Recovery Bay the booster is horizontal and ticking.', image_url: placeholderImage('world-d', 'moss') }, player_pos: { x: 1, y: 7 }, chosen: 'Refuse until the vent cycle completes' },
    ],
  },
};
