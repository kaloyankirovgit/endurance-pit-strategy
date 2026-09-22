---
name: research-literature
description: Read a paper or reference implementation and record what it changes for this project. Use before designing a component that the literature has already addressed - simulator design, strategy optimisation, traffic modelling.
---

# Research literature

Read to make a better design decision, not to summarise. A paper earns an entry in `docs/research/literature.md` when it changes something — or when it explicitly fails to.

---

## 1. Before reading

State the design question the paper is being read to answer. Without one, the notes become a summary that is never used.

Check the reading queue in `docs/research/literature.md` — read what the current layer needs, not what is most interesting.

## 2. Extract

- **Research question** — what the authors set out to answer
- **Methodology** — data, model, evaluation design
- **Useful result** — the specific finding or technique worth having
- **Limitation** — what it does not establish; where it would not transfer
- **Relevance here** — what this changes in our design. "Interesting" is not relevance.

## 3. Transfer critically

Most race-strategy literature is single-class Formula 1 with telemetry access. This project is multi-class endurance racing with timing data only. Before adopting anything, ask:

- Does the method depend on data we do not have?
- Does it assume a single class?
- Does it assume a controlled simulator rather than observational data?
- Would its validation design pass our own standards? (Several published papers use random lap-level splits.)

A method that cannot transfer is still worth recording — the reason it cannot is often the sharpest statement of our own constraints.

## 4. Check the numbers

Do not import a figure as a justification without checking what it means. The ~99,928-lap figure in the Sasikumar et al. paper is a scale reference, **not** evidence that a lap count confers statistical validity — those laps are clustered within races, cars and drivers.

## 5. Licensing

For a reference implementation, check the licence **before** reusing code or substantial implementation patterns. Record the licence in the notes.

## 6. Record

Write the entry in `docs/research/literature.md` using its template. If the paper changes an architectural choice, add a decision entry in `docs/DECISIONS.md` citing it.

---

## Watch for

**Reading in order of interest rather than need.** The RL papers are the most interesting and the least immediately useful — they are stretch references (see DECISIONS D-007).

**Adopting an architecture because it is published.** Reference implementations are built for their authors' data and constraints.

**Citing a paper not actually read.** A citation in this repository means the source was retrieved and read.
