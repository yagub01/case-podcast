# Course profiles

Each course is one Markdown file in this folder, for example `strategy.md`. The app reads every `.md` file here except this README.

To create a profile, paste the prompt below into the Claude chat or project where you discussed that course, then save its answer here as a new `.md` file.

```
I am building a study tool that turns HBS cases into prep briefs and podcasts. I need a course profile for this course, based on the syllabus and everything we have discussed in this conversation or project.

Rules:
- Use only information from the syllabus, the project files, and our conversations. Do not invent anything.
- Where information is missing, write "Unknown".
- Name frameworks, cases, and concepts exactly as the course names them.
- Output only the profile, inside a single code block, so I can copy it cleanly.

Use exactly this structure:

# Course: [full course name]
- Code:
- Professor(s):
- Term:

## Course purpose
[2–4 sentences on what the course teaches and why.]

## Core frameworks and concepts
- **[Framework name]:** [one line on what it is and how the course uses it]
[Repeat for each framework or concept.]

## Professor's emphasis
[What the professor stresses in class, such as quantitative analysis, taking a firm position, ethics, or implementation. Include how cold calls and class participation work, if known.]

## Sessions
### Session [number]: [title] ([date])
- Case(s):
- Readings:
- Topic and learning objective:
- Frameworks applied:
- Assignment questions: [if any were given; otherwise "None"]
- Notes: [anything relevant from our discussions about this session]
[Repeat for every session in the syllabus.]
```
