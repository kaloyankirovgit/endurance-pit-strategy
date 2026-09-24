---
name: humanizer
description: Rewrite CV bullets, project summaries and other prose so they read as written by Kaloyan, not an AI. Use for any CV, cover-letter, README-summary or LinkedIn wording, and whenever he types /humanizer.
---

# Humanizer

Make the text sound like a person wrote it. Apply to anything destined for his CV, `docs/cv/CV_SECTIONS.md`, a cover letter or a public summary.

## Kaloyan's house style (overrides generic humanizer advice)

- **No em dashes, ever.** Not `—` and not LaTeX `---`. Use a full stop, a comma or "and" instead.
- **Lists are bullet points.** Never a bold label followed by a dash and a description. Put the label on one bullet and the detail on a sub-bullet, or use "**Label:** description".
- **Plain, normal words.** Say "built", "used", "found", "tested". Not "leveraged", "spearheaded", "harnessed", "robust", "seamless", "cutting-edge", "comprehensive", "pivotal", "delve", "showcase", "underscore", "landscape", "tapestry".
- **Never write "genuinely".** Also drop its cousins: "truly", "really", "deeply", "incredibly".
- **No lists of three.** No "X, Y and Z" triplets of adjectives, verbs or nouns, and no three-beat sentence rhythm. Use two items, or four, or restructure into one concrete claim.

## Other AI tells to remove

- Inflated significance ("a testament to", "plays a key role in", "marks a shift").
- Trailing "-ing" analysis clauses ("..., highlighting the importance of ...").
- Negative parallelism ("not just X, but Y"; "it's not about X, it's about Y").
- Vague attribution ("experts say", "widely regarded").
- Filler connectors ("Moreover", "Furthermore", "Additionally", "In addition").
- Promotional tone and stacked adjectives.
- Bold-colon mini-headings inside prose.

## Process

1. Read the text once for meaning. Keep every fact, number and qualifier.
2. Rewrite sentence by sentence against the rules above.
3. Scan the result: count triplets, search for "genuinely" and for em dashes, check no banned words slipped back in.
4. Prefer shorter. A CV bullet is one line where possible: action, scale, method, outcome.

## Output

Return the rewritten text only, unless he asks what changed.
