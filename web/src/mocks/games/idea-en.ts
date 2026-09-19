import type { MockGame } from '../types';
import { mapIdea, startPos } from '../maps';
import { placeholderImage } from '../placeholder';

const map = mapIdea(['The Lamp Room', 'The Jetty', "Postmaster's Hut", 'The Cellar', 'The Tide Line']);

export const ideaEn: MockGame = {
  id: 'mock-idea-en',
  request: {
    mode: 'idea',
    idea: 'a lighthouse keeper who keeps receiving letters meant for someone else',
    story_language: 'en',
    ui_language: 'en',
  },
  state: {
    game_id: 'mock-idea-en',
    mode: 'idea',
    view: 'scene',
    story_language: 'en',
    ui_language: 'en',
    safety_class: 'allowed',
    style_card: {
      genre: 'folk_tale',
      narrative_voice: 'second_present',
      tone: 'lyrical',
      protagonist_role: 'outsider',
      visual_style: 'ink_wash',
      music_mood: 'drone',
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
        'The boat comes on Thursdays and it has never once brought you a letter. It brings letters ' +
        'for a man named Aldous Frey, who according to every record you can find has not kept this ' +
        'light since 1911. You have forty-one of them now, in a tin, under the [KEY:stairs].',
      image_url: placeholderImage('start-idea-en', 'dusk'),
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
        'In [LOC:the lamp room] the glass is warm even when it should not be. You have oiled the ' +
        'track, trimmed what needs trimming, and still the beam hesitates once every turn, as ' +
        'though it were looking for something specific out there and not finding it.',
      image_url: placeholderImage('idea-en-a', 'dusk'),
    },
    'loc-b': {
      id: 'sc-b',
      location_id: 'loc-b',
      text:
        'The [LOC:jetty] is slick and the water underneath it makes a sound like paper being ' +
        'shuffled. This is where the boat leaves the sack. Today there is a letter on the boards ' +
        'themselves, weighted with a stone, already addressed in the same careful hand.',
      image_url: placeholderImage('idea-en-b', 'cold'),
    },
    'loc-c': {
      id: 'sc-c',
      location_id: 'loc-c',
      text:
        "The [POI:postmaster] keeps his hut warm enough to be rude about it. He knows the name. He " +
        'says it the way people say the name of a road that flooded. He asks you, carefully, how ' +
        'many letters there are now, and writes the number down.',
      image_url: placeholderImage('idea-en-c', 'rust'),
    },
    'loc-d': {
      id: 'sc-d',
      location_id: 'loc-d',
      text:
        'The [LOC:cellar] smells of iron and cold salt. Behind the coal there is a second tin, ' +
        'older than yours, with forty-one letters in it, none of them opened. The handwriting on ' +
        'the outermost one is unmistakably, impossibly, your own.',
      image_url: placeholderImage('idea-en-d', 'ash'),
    },
    'loc-e': {
      id: 'sc-e',
      location_id: 'loc-e',
      text:
        'At the [LOC:tide line] the sea has arranged the night\'s losses in a neat grey row, the ' +
        'way it always does. Among the kelp there is a postbag, canvas gone stiff with salt, the ' +
        'buckle still shut. It is not this year\'s. It is not this century\'s.',
      image_url: placeholderImage('idea-en-e', 'moss'),
    },
  },
  choices: {
    'loc-a': [
      { id: 'a1', text: 'Follow where the beam hesitates' },
      { id: 'a2', text: 'Re-seat the lens and ignore it' },
      { id: 'a3', text: 'Read a letter by lamplight' },
    ],
    'loc-b': [
      { id: 'b1', text: 'Take the weighted letter' },
      { id: 'b2', text: 'Leave it and watch who comes' },
      { id: 'b3', text: 'Write "NOT HERE" and set it back' },
    ],
    'loc-c': [
      { id: 'c1', text: 'Ask who Aldous Frey was' },
      { id: 'c2', text: 'Ask why the postmaster keeps count' },
      { id: 'c3', text: 'Hand over the whole tin' },
    ],
    'loc-d': [
      { id: 'd1', text: 'Open the outermost letter' },
      { id: 'd2', text: 'Put the coal back exactly as it was' },
      { id: 'd3', text: 'Carry both tins up to the light' },
    ],
    'loc-e': [
      { id: 'e1', text: 'Open the bag here, in the wind' },
      { id: 'e2', text: 'Carry it up unopened' },
      { id: 'e3', text: 'Put it back where the sea left it' },
    ],
  },
  openQuestionAt: 'loc-a',
  ending: {
    game_id: 'mock-idea-en',
    mode: 'idea',
    title: 'Forty-one letters, twice',
    summary:
      'You read one by lamplight before you understood what reading it would cost, then went down ' +
      'and found the other tin anyway. You carried both up to the light. The beam stopped ' +
      'hesitating. Whatever it had been looking for was, by then, in the room with it.',
    canon: [],
    player: [
      { beat_id: 'b1', status: 'matched', what_you_did: 'You read a letter by lamplight.' },
      { beat_id: 'b2', status: 'matched', what_you_did: 'You took the weighted letter off the jetty.' },
      { beat_id: 'b3', status: 'diverged', what_you_did: 'You asked why the postmaster keeps count.' },
      { beat_id: 'b4', status: 'matched', what_you_did: 'You carried both tins up to the light.' },
      { beat_id: 'b5', status: 'matched', what_you_did: 'You carried the sea-found postbag up unopened.' },
    ],
    style_card: {
      genre: 'folk_tale',
      narrative_voice: 'second_present',
      tone: 'lyrical',
      protagonist_role: 'outsider',
      visual_style: 'ink_wash',
      music_mood: 'drone',
      pacing: 'slow_burn',
    },
    sources: [],
  },
  replay: {
    game_id: 'mock-idea-en',
    title: 'Forty-one letters, twice',
    turns: [
      { turn: 1, scene: { id: 'sc-a', location_id: 'loc-a', text: 'In the lamp room the glass is warm even when it should not be.', image_url: placeholderImage('idea-en-a', 'dusk') }, player_pos: { x: 1, y: 5 }, chosen: 'Read a letter by lamplight', answer: 'That he was sorry, and that he would not be on the Thursday boat after all.' },
      { turn: 2, scene: { id: 'sc-b', location_id: 'loc-b', text: 'The jetty is slick and the water underneath makes a sound like paper.', image_url: placeholderImage('idea-en-b', 'cold') }, player_pos: { x: 8, y: 1 }, chosen: 'Take the weighted letter' },
      { turn: 3, scene: { id: 'sc-c', location_id: 'loc-c', text: 'The postmaster keeps his hut warm enough to be rude about it.', image_url: placeholderImage('idea-en-c', 'rust') }, player_pos: { x: 12, y: 6 }, chosen: 'Ask why the postmaster keeps count' },
      { turn: 4, scene: { id: 'sc-d', location_id: 'loc-d', text: 'The cellar smells of iron and cold salt.', image_url: placeholderImage('idea-en-d', 'ash') }, player_pos: { x: 6, y: 7 }, chosen: 'Carry both tins up to the light' },
    ],
  },
};
