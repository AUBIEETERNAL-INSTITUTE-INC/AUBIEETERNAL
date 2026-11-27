# Open-Source Learning Ideas for AUBIEETERNAL Institute

**Status:** Planning ideas only. Draft on disk. No upstream code was copied into this repository.  
**Verified:** 27 Nov 2026 (America/New_York). Each project's live GitHub repository, license file, and README were checked on that date.  
**Brand:** AUBIEETERNAL Institute only. Keep Family Co-Learning voice, local-first family privacy, and pretend tokens only for kids. No investment advice.

---

## Purpose and Scope

This note records verified ideas from six open-source learning projects (MIT or Apache-2.0) that can inspire future AUBIEETERNAL Institute Family Co-Learning tools:

- interactive models and guided walkthroughs
- printable family storybooks
- math and physics concept animations
- guided practice with a notebook of misses
- multi-role learning rooms with narration, simulations, mini-games, and quizzes
- family language practice with voice, flashcards, and spaced repetition

These are **inspiration and adaptation ideas**, not a plan to vendor, fork, or ship any of the six projects as-is. If Institute authors later reuse any upstream code, they must keep the original MIT or Apache-2.0 license text, copyright notice, and attribution, and they must follow any extra terms that apply to bundled third-party packages.

Every future tool built from these ideas should stay inside Institute guardrails:

- nonpartisan educational mission
- local-first family privacy, with no personal data collected from kids
- pretend tokens only for kids — no real money and no real sats
- no investment advice
- wording for learners and families (not institutional labels)

---

## Summary of the six verified projects

| Project | License (verified) | Core idea (from the live repository) | How it can fit AUBIEETERNAL Institute |
|---|---|---|---|
| [VisualLearning.Skill](https://github.com/andrewalumkal/VisualLearning.Skill) | MIT | A skill that helps an AI agent build sourced, animated visual explainers: narrated walkthroughs and interactive explorers, as single HTML files | Interactive *What is Money* models such as Maya's Lemonade Market and the Shared Notebook Game |
| [StoryCraft](https://github.com/cn-vhql/StoryCraft) | MIT | An AI picture-book maker for ages 3–5, with Chinese–English bilingual pages, several art styles, and PDF export | Printable Maya family storybooks for younger learners, reviewed by a parent before use |
| [Math-To-Manim](https://github.com/HarleyCoops/Math-To-Manim) | MIT | A toolkit that turns text and images into math and physics animations and study notes, including verified 3D Manim and Blender films from one command-line run | Step-by-step concept films for family lessons (start with simple ideas, not frontier research films) |
| [DeepTutor](https://github.com/HKUDS/DeepTutor) | Apache-2.0 | A personalized tutoring workspace with chat, quizzes, a mastery path, practice that stores misses, and a learning notebook, grounded in a family's own materials | A 1-on-1, lesson-grounded guide for Institute packs, with practice questions and a notebook of misses, run locally |
| [OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) | MIT (root license; see note below) | A multi-agent platform that turns a topic or document into an interactive learning experience with slides, quizzes, simulations, games, narration, and offline export | A family learning room with several AI roles, narration, simulations, mini-games, and quizzes, exportable for offline use |
| [OpenLingo](https://github.com/pretzelai/openlingo) | MIT | An open language-learning platform with an AI conversation guide, exercises, spaced-repetition flashcards, voice practice, and translated reading, described as supporting 15+ languages | Family language tracks with voice practice, flashcards, and spaced repetition, kept local-friendly and free of kid-data collection |

**License note for OpenMAIC:** The root repository license is MIT. The project's README also states that two bundled workspace packages keep their own terms: `packages/mathml2omml` (LGPL-3.0-or-later) and `packages/pptxgenjs` (MIT). If the repository is ever redistributed as a whole, those package terms apply to those files.

---

## 1. VisualLearning.Skill

**Repository:** [https://github.com/andrewalumkal/VisualLearning.Skill](https://github.com/andrewalumkal/VisualLearning.Skill)  
**Verified license:** MIT (LICENSE file and GitHub SPDX: MIT). The GitHub repository description field is empty; the facts below come from the live README.

### What the project does

VisualLearning.Skill is a set of Markdown instructions, plus two example HTML files, that teach an AI agent to build animated visual explainers for a subject with moving parts or steps in order. It is not tied to one AI model or tool.

It builds two formats that work together:

- **Guided walkthroughs:** narrated, chaptered animations that build a picture step by step, with captions, a scrubber, speed control, chapter buttons, and a pause after each step.
- **Interactive explorers:** switchable views of one shared model, with drill-down, controls, and plain-language tooltips.

The README says every fact shown is checked against real sources, and each explainer lists those sources on the page. Before building, the agent proposes two or three approaches and waits for a person to pick one. After each part is built, a reviewer checks the claims, how well the explainer teaches, and how it behaves in a browser. Each example is a single HTML file with no build step.

One of the project's own example prompts is "Show me how compound interest grows," which sits close to *What is Money* themes.

### AUBIEETERNAL Institute adaptation idea

Build Institute-authored, source-listed HTML explainers for the *What is Money* series, starting with:

- **Maya's Lemonade Market** (Lesson 4): a guided walkthrough of what happens when one note keeper adds more pretend notes, and why the Later jar buys less.
- **The Shared Notebook Game** (Lesson 5): an interactive explorer of a shared pretend notebook with a public supply rule, so a family can step through writes, checks, and the four-check scorecard.

Keep these as simple local HTML files a family can open on their own computer. List sources on the page, just as the upstream skill requires.

### Guardrails and license compliance

If any instructions or HTML patterns from VisualLearning.Skill are reused, keep the MIT copyright notice, permission notice, and attribution. Prefer fully local files with no analytics and no account sign-in. Use pretend tokens only. Do not treat a visual model as investment advice.

---

## 2. StoryCraft

**Repository:** [https://github.com/cn-vhql/StoryCraft](https://github.com/cn-vhql/StoryCraft)  
**Verified license:** MIT (LICENSE file and GitHub SPDX: MIT).  
**Verified description:** "AI-powered children's picture book generator for ages 3-5".

### What the project does

StoryCraft is a Streamlit app (Python 3.11+) that helps a family turn a short idea into a picture book for ages 3–5. The live README lists these features:

- AI story generation from a creative idea
- automatic illustrations for each page
- bilingual support in Chinese and English
- PDF export, described as optimized for Kindle e-readers and tablets
- several art styles (the README describes eight, including manga, anime, Chinese traditional, watercolor, cartoon, oil painting, and classical)
- the ability to edit the story and regenerate images

The default story flow generates Chinese text first, then translates scenes to English when illustrations are made. The upstream app uses third-party cloud AI services (the README recommends Tongyi Qianwen, with Doubao as another option) and asks parents to review AI-generated content before reading it with children. README files are also provided in Simplified Chinese and Japanese.

### AUBIEETERNAL Institute adaptation idea

Create short, printable Maya family storybooks that retell *What is Money* moments for younger learners — for example, Maya's lemonade stand, the Later jar, and a shared notebook — in plain language, with parent-reviewed art and a PDF a family can print or read on a tablet.

A bilingual edition is a good later step. Upstream StoryCraft is Chinese and English; an Institute edition could start in English and add a second language a family actually uses, without claiming the upstream tool already speaks every language.

### Guardrails and license compliance

If any StoryCraft code is later reused, keep the MIT copyright notice, permission notice, and attribution. Prefer local or parent-controlled generation over sending a child's name, photo, or personal details to a cloud API. A parent should review every page before a child hears or reads it. Keep money examples in pretend tokens only. Do not invent sources or historical claims inside a storybook; if a story points to a real event, mark unsourced facts for later checking or leave them out.

---

## 3. Math-To-Manim

**Repository:** [https://github.com/HarleyCoops/Math-To-Manim](https://github.com/HarleyCoops/Math-To-Manim)  
**Verified license:** MIT (LICENSE file and GitHub SPDX: MIT).  
**Verified GitHub description:** "Create Epic Math and Physics Animations & Study Notes From Text and Images."

### What the project does

The live README says Math-To-Manim turns frontier mathematics into verified 3D Manim and Blender films in a single command-line run. The GitHub description also covers study notes, and the README shows that a film can start from text or from a photograph of a notebook sketch.

The public showcase is mostly advanced mathematics and physics films (with numerical checks, scene checks, and published run records). That is what the project actually demonstrates today. It is a strong technical reference for "idea in, checked animation out," not a ready-made library of early-family lessons.

### AUBIEETERNAL Institute adaptation idea

Use the same *idea → checked visual → short family film or notes* pattern for Institute concepts, at a much simpler level:

- Lesson 4 purchasing-power pictures (one lemonade, then more notes, then a higher pretend price)
- Lesson 5 shared-notebook pictures (matching copies, a public rule, a new line added only after checks)
- later math and physics explainers in Institute learning paths, always with sources and a parent layer

Start with short, plain films and stills a family can pause. Do not import the upstream showcase's frontier-research claims into Institute lessons.

### Guardrails and license compliance

If any Math-To-Manim code, prompts, or scene patterns are reused, keep the MIT copyright notice, permission notice, and attribution. Treat every on-screen number as something that must be checked. Keep renders local when practical. No personal data from kids. No investment advice. Pretend tokens only in money examples.

---

## 4. DeepTutor

**Repository:** [https://github.com/HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor)  
**Verified license:** Apache License 2.0 (LICENSE file and GitHub SPDX: Apache-2.0).  
**Verified description:** "DeepTutor: Lifelong Personalized Tutoring."

### What the project does

The live README describes DeepTutor as an agent-native learning workspace that connects tutoring, research, creation, and practice in one system. Shared modes include Chat, Quiz, Research, Visualize, Solve, Mastery Path, and Reading.

A connected workspace links Chat, Books, Reading, Practice, a Task Board, a Calendar, and a Learning notebook, with shared materials and progress. Knowledge bases can ground answers in documents the family provides, with source-linked citations.

The README's activity table is the most precise feature list for Institute planning:

- **Mastery Path:** break a learning goal into topics and guided study, keeping a knowledge-point map, topic conversations, and mastery evidence.
- **Practice:** review collected or imported questions, keeping answers, mistakes, recall ratings, and the next review date.
- **Book** and **Immersive Reading:** structured reading beside sources, with notes and progress.

Release notes also mention a Question Notebook (bookmarks and categories), question-bank practice, and a learning journal. The README does not use the exact name "mistake notebook"; the verified behavior is that Practice stores misses, recall ratings, and the next review date, beside a Learning notebook and a Question Notebook.

DeepTutor can run as a local web app or desktop preview, including Docker on the local computer.

### AUBIEETERNAL Institute adaptation idea

Add a **lesson-grounded family guide** for Institute packs (starting with *What is Money* and the Meta Apps safety lesson):

- answers and hints stay tied to the written lesson, not to free-floating chat
- practice questions a parent and child can do together
- a **notebook of misses** (inspired by DeepTutor's Practice records): what was missed, a plain-language hint, and when to try again
- a short study path through the six *What is Money* lessons

Follow existing Institute tutor rules: never confirm a guess, skip fake praise, and let a hint give the first step only. Keep the guide optional and parent-supervised.

### Guardrails and license compliance

If any DeepTutor code is later reused, keep the Apache-2.0 license, notices, and attribution, and state any changes. Run it locally. Do not send a child's chat, name, or work to a third-party host. Do not collect personal data from kids. Ground answers in Institute lessons and their Sources sections. Pretend tokens only. No investment advice.

---

## 5. OpenMAIC

**Repository:** [https://github.com/THU-MAIC/OpenMAIC](https://github.com/THU-MAIC/OpenMAIC)  
**Verified license:** MIT for the root project (LICENSE file, GitHub SPDX: MIT, and a README note that the project was relicensed to MIT in v0.3.0). Bundled package terms are noted in the summary table above.  
**Verified GitHub description:** an open multi-agent interactive learning experience that can be started in one click. In Institute writing, describe this as a **multi-agent learning room** or **study space**.

### What the project does

The live README says OpenMAIC turns a topic or document into a rich, interactive, multi-agent learning experience. A person can describe a topic or attach materials; the system builds a lesson with an outline and then scenes.

Verified scene and interaction types include:

- slides with voice narration
- quizzes (including multiple choice and short answer) with live feedback
- interactive HTML simulations
- project-based activities with milestones
- a whiteboard, plus text-to-speech so agents can explain out loud
- Deep Interactive Mode, which adds 3D views, simulations, knowledge-based mini-games, mind maps, and in-browser coding

Agents can present, discuss, and interact in real time. Lessons can be exported as PowerPoint, as one offline HTML file, or as a ZIP. The README says a later export can inline outside assets so the lesson plays offline after import, without contacting a public content network at playback time. Optional local components mentioned in the README include a local AI provider (Lemonade) and local speech recognition (FunASR).

### AUBIEETERNAL Institute adaptation idea

Design a **family learning room** for Institute lessons: one parent-guided space where a narrator, a quiz guide, and a "try it" helper take turns. For *What is Money*, that room could hold a lemonade-market simulation, a shared-notebook mini-game, short quizzes, and a spoken walkthrough. Export an offline HTML or ZIP so a family can run it on a home computer without an always-on network.

### Guardrails and license compliance

If OpenMAIC code is later reused, keep the root MIT notice and also honor the LGPL-3.0-or-later terms on `packages/mathml2omml` and the MIT terms on `packages/pptxgenjs` when those packages are included. Prefer local models and offline export. Do not collect personal data from kids. Keep Institute wording in the family-facing experience (learning room, study space, adult guide, learners). Pretend tokens only. No investment advice.

---

## 6. OpenLingo

**Repository:** [https://github.com/pretzelai/openlingo](https://github.com/pretzelai/openlingo)  
**Verified license:** MIT (LICENSE file and GitHub SPDX: MIT).  
The GitHub repository description field is empty; the facts below come from the live README. A public demo is listed at [https://openlingo.dev](https://openlingo.dev).

### What the project does

The README describes OpenLingo as a free, open-source, AI-powered language-learning platform. People can practice through conversations with an AI guide, interactive exercises, spaced-repetition flashcards, and translated reading material.

The README says the platform supports 15+ languages. The languages it lists by name are German, French, Spanish, Italian, Portuguese, Russian, Arabic, Hindi, Korean, Mandarin Chinese, Japanese (Hiragana, Katakana, and Kanji), and English, with pre-loaded frequency dictionaries and CEFR labels.

Verified tools and practice types include:

- a conversation guide that can adapt, keep notes, and create exercises
- spaced repetition using the SM-2 algorithm, with card states of new, learning, and review
- nine exercise types, including multiple choice, translation, fill in the blank, matching pairs, listening (text-to-speech), word bank, speaking (speech-to-text with feedback), free-text writing, and flashcard review
- courses and units stored as Markdown
- reading: paste a web article address, then get a paragraph-by-paragraph translation at a chosen CEFR level, with optional audio

The documented default stack uses a web app, a database, sign-in, cloud AI, and cloud audio storage. That hosted default is **not** a drop-in fit for Institute family privacy. The useful ideas are the practice patterns (conversation, voice, flashcards, spaced repetition), which can be rebuilt in a local-friendly way.

### AUBIEETERNAL Institute adaptation idea

Add optional **family language tracks** beside Institute lessons: short spoken practice, flashcards, and spaced repetition for words and phrases a family actually wants to learn, including bilingual retellings of Maya stories. Keep audio and progress on the family's own computer. Do not require a child's account or cloud sign-in.

### Guardrails and license compliance

If any OpenLingo code is later reused, keep the MIT copyright notice, permission notice, and attribution. Do not copy the hosted sign-in or cloud-audio design for kids. No personal data collection from kids. A parent should be able to turn voice features off. Keep Institute lessons nonpartisan, and keep money examples in pretend tokens only.

---

## Suggested Phased Roadmap

This is a suggested order only. Each phase should stay draft-first, local-first, and Institute-branded.

### Phase 1 — Quick wins: interactive models and printable storybooks

- HTML guided walkthroughs and interactive explorers for Maya's Lemonade Market and the Shared Notebook Game, in the VisualLearning.Skill pattern (sources on the page, step-by-step pause and play).
- Parent-reviewed, printable Maya family storybooks for younger learners, with PDF export. Start in English; add a second language when a family edition is ready.
- If animation capacity allows, begin one or two short Math-To-Manim-style concept films for Lessons 4 and 5, with every number checked.

### Phase 2 — Guided practice and a notebook of misses

- A lesson-grounded family guide, inspired by DeepTutor, that stays inside written Institute lessons.
- Practice questions, a notebook of misses, and a gentle study path through *What is Money* and later packs.
- More math and physics concept animations and study notes, still at family level, with sources.

### Phase 3 — Family learning rooms and language tracks

- A multi-role family learning room, inspired by OpenMAIC, with narration, simulations, mini-games, quizzes, and offline export.
- Family language tracks, inspired by OpenLingo, with voice practice, flashcards, and spaced repetition, all local-friendly.

No phase should start training a public model, posting to social platforms, or pushing to GitHub on its own. Institute posts stay draft-only for Matthew or Gabriela to review and post.

---

## Shared Institute Guardrails (every phase)

1. **License and attribution.** Reuse of code requires keeping the upstream MIT or Apache-2.0 license, copyright notice, and attribution, plus any bundled third-party terms (see OpenMAIC above). This ideas note itself copies no source code.
2. **Local-first privacy.** Tools should work offline or on a family's own computer when practical. Do not collect personal data from kids. Do not build ads or personality scores.
3. **Pretend tokens only for kids.** No real money and no real sats in family activities.
4. **No investment advice.** Lessons may explain ideas and tradeoffs; they may not tell a family what to buy or hold.
5. **Family wording.** Write for learners and families. Use "learning room" or "study space," never institutional labels.
6. **Check sources.** Do not invent features, figures, or history. Mark unsourced facts for later checking, or leave them out.
7. **Nonpartisan educational mission.** Keep AUBIEETERNAL Institute branding and links only.

---

## Verified Sources

All six repositories were live on **27 Nov 2026**. Licenses were confirmed from each GitHub repository's SPDX license field and from the LICENSE file on the default branch. Feature claims were taken from each project's live README (and the GitHub description field when it was not empty).

| Project | GitHub repository | License file (default branch) | Other official pages checked |
|---|---|---|---|
| VisualLearning.Skill | [https://github.com/andrewalumkal/VisualLearning.Skill](https://github.com/andrewalumkal/VisualLearning.Skill) | [LICENSE](https://github.com/andrewalumkal/VisualLearning.Skill/blob/main/LICENSE) (MIT) | [README](https://github.com/andrewalumkal/VisualLearning.Skill/blob/main/README.md) |
| StoryCraft | [https://github.com/cn-vhql/StoryCraft](https://github.com/cn-vhql/StoryCraft) | [LICENSE](https://github.com/cn-vhql/StoryCraft/blob/master/LICENSE) (MIT) | [README](https://github.com/cn-vhql/StoryCraft/blob/master/README.md) |
| Math-To-Manim | [https://github.com/HarleyCoops/Math-To-Manim](https://github.com/HarleyCoops/Math-To-Manim) | [LICENSE](https://github.com/HarleyCoops/Math-To-Manim/blob/main/LICENSE) (MIT) | [README](https://github.com/HarleyCoops/Math-To-Manim/blob/main/README.md) |
| DeepTutor | [https://github.com/HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor) | [LICENSE](https://github.com/HKUDS/DeepTutor/blob/main/LICENSE) (Apache-2.0) | [README](https://github.com/HKUDS/DeepTutor/blob/main/README.md) |
| OpenMAIC | [https://github.com/THU-MAIC/OpenMAIC](https://github.com/THU-MAIC/OpenMAIC) | [LICENSE](https://github.com/THU-MAIC/OpenMAIC/blob/main/LICENSE) (MIT) | [README](https://github.com/THU-MAIC/OpenMAIC/blob/main/README.md) |
| OpenLingo | [https://github.com/pretzelai/openlingo](https://github.com/pretzelai/openlingo) | [LICENSE](https://github.com/pretzelai/openlingo/blob/main/LICENSE) (MIT) | [README](https://github.com/pretzelai/openlingo/blob/main/README.md); project site [https://openlingo.dev](https://openlingo.dev) |

**Verification notes (where the live record differs from a shorter summary):**

- VisualLearning.Skill and OpenLingo have empty GitHub description fields; use the README, not an invented one-line blurb.
- DeepTutor's verified Practice feature stores answers, mistakes, recall ratings, and the next review date. It also has a Learning notebook and a Question Notebook. It does not, in the README checked on 27 Nov 2026, use the exact product name "mistake notebook."
- OpenMAIC's root license is MIT, with the bundled-package exception recorded above.
- OpenLingo's README says "15+ languages" and lists the twelve language names above. This note does not invent the remaining names.
- Math-To-Manim's public showcase is advanced mathematics and physics. Institute use should stay at family-lesson level and should not import unverified research claims.
