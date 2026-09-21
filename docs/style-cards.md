# Style cards

Generated from `app/pipeline/style_catalog.py`.

## `genre`

| id | pl | en | prompt fragment | safe mode |
|---|---|---|---|---|
| `noir` | noir | noir | hard-boiled noir: short sentences, moral fog, rain and sodium light | yes |
| `folk_tale` | baśń | folk tale | an oral folk tale: repetition, omens, plain words holding strange things | yes |
| `procedural` | proceduralny | procedural | a procedural: competence, jargon used correctly, process as tension | yes |
| `absurdist` | absurd | absurdist | absurdist: deadpan impossible logic followed rigorously | no |
| `epic` | epicki | epic | epic register: scale, weather, consequence beyond the protagonist | yes |
| `documentary` | dokument | documentary | documentary realism: verified detail, restraint, no authorial flourish | yes |
| `pastoral` | pastoralny | pastoral | pastoral: landscape as a character, slow attention to ordinary work | yes |
| `gothic` | gotycki | gothic | gothic: architecture that watches, inheritance, dread under politeness | yes |

## `narrative_voice`

| id | pl | en | prompt fragment | safe mode |
|---|---|---|---|---|
| `second_present` | druga osoba, teraz | second person, present | second person present tense ('you walk') | yes |
| `first_past` | pierwsza osoba, przeszła | first person, past | first person past tense ('I walked') | yes |
| `third_close` | trzecia osoba, bliska | third person, close | close third person, fixed to the protagonist's senses | yes |
| `chorus` | chór | chorus | a collective 'we' that speaks for the people present | yes |

## `tone`

| id | pl | en | prompt fragment | safe mode |
|---|---|---|---|---|
| `dry` | oschły | dry | dry and unsentimental; let facts do the work | yes |
| `lyrical` | liryczny | lyrical | lyrical; image-led sentences, but never ornate for its own sake | yes |
| `tense` | napięty | tense | tense; short clauses, withheld information, physical detail | yes |
| `warm` | ciepły | warm | warm; attentive to small kindnesses and to what people carry | yes |
| `deadpan` | beznamiętny | deadpan | deadpan; report the extraordinary in the register of a timetable | no |
| `reverent` | pełen szacunku | reverent | reverent; measured, unhurried, conscious of what is at stake | yes |

## `protagonist_role`

| id | pl | en | prompt fragment | safe mode |
|---|---|---|---|---|
| `participant` | uczestnik | participant | the protagonist is caught up in this directly | yes |
| `witness` | świadek | witness | the protagonist watches and records, and mostly cannot intervene | yes |
| `rescuer` | ratownik | rescuer | the protagonist's job is to get people out | yes |
| `official` | urzędnik | official | the protagonist carries an official responsibility and its constraints | yes |
| `journalist` | dziennikarz | journalist | the protagonist is reporting, and must decide what to publish | yes |
| `outsider` | obcy | outsider | the protagonist does not belong here and reads everything slightly wrong | yes |
| `volunteer` | wolontariusz | volunteer | the protagonist turned up to help without being asked to | yes |

## `visual_style`

| id | pl | en | prompt fragment | safe mode |
|---|---|---|---|---|
| `pixel` | pixel art | pixel art | low-resolution pixel art, limited palette, chunky dithering | no |
| `ink_wash` | tusz | ink wash | monochrome ink wash painting, wet edges, large areas of empty paper | yes |
| `grainy_photo` | ziarnista fotografia | grainy photo | grainy 35mm photograph, available light, slight motion blur | yes |
| `blueprint` | rysunek techniczny | blueprint | cyanotype blueprint: white line on deep blue, annotated | yes |
| `woodcut` | drzeworyt | woodcut | high-contrast woodcut print, carved lines, no midtones | yes |
| `oil_sketch` | szkic olejny | oil sketch | loose oil sketch on toned ground, visible brushwork | yes |
| `risograph` | riso | risograph | two-colour risograph print, misregistered layers, paper texture | yes |

## `music_mood`

| id | pl | en | prompt fragment | safe mode |
|---|---|---|---|---|
| `drone` | dron | drone | a single sustained drone, almost no movement | yes |
| `pulse` | puls | pulse | a slow repeating pulse, minimal and mechanical | yes |
| `elegy` | elegia | elegy | an elegy: strings, falling intervals, space between phrases | yes |
| `march` | marsz | march | a restrained march, low percussion, steady tread | yes |
| `shimmer` | migotanie | shimmer | high shimmering texture, bells and bowed metal | yes |
| `static` | szum | static | filtered static and room tone, barely musical | yes |

## `pacing`

| id | pl | en | prompt fragment | safe mode |
|---|---|---|---|---|
| `slow_burn` | powolny | slow burn | slow burn: let scenes breathe, escalate late | yes |
| `staccato` | urywany | staccato | staccato: quick cuts, each scene one hard beat | yes |
| `escalating` | narastający | escalating | escalating: each scene raises the stakes over the last | yes |
