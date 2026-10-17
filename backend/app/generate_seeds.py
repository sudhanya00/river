"""Draft "from the river" seed messages with Claude Haiku for a person to review.

    python -m app.generate_seeds [count]      # default 40

Writes candidates to backend/seeds/candidates.txt (gitignored). Nothing reaches the river until a
person copies the ones they approve into app/seeds.txt and runs `python -m app.seed`.

Needs the dev-only `anthropic` package (requirements-dev.txt) and credentials from ANTHROPIC_API_KEY
or an `ant auth login` profile. A run of 40 costs well under a cent.
"""
import sys
from pathlib import Path

import anthropic
from pydantic import BaseModel

from .seed import SEEDS_FILE, parse, problems

MODEL = "claude-haiku-5-5"
OUT = Path(__file__).resolve().parents[1] / "seeds" / "candidates.txt"

PROMPT = """River is an app where people drop short anonymous messages into a shared "river" and \
strangers catch them one at a time. When someone has read every message people have written, they \
start catching messages "from the river" itself, labelled that way in the app. Write {count} of those.

What they are: affirmations, words of wisdom, and gentle nudges a stranger would be glad to catch \
on an ordinary day. Mostly Indian readers, so everyday Indian life (chai, monsoon, trains, family, \
exams, first jobs, moving cities) is welcome where it fits, without forcing it.

How they should read:
- Specific and plain, not greeting-card. "Drink some water, then go outside for five minutes" beats \
"You are enough." Short sentences. A little dry humour is fine.
- Speak to the reader or about life in general. They are labelled as coming from the river, so do \
not invent first-person life stories ("I quit my job...") that pretend a real person wrote them.
- No emojis, hashtags, quotation marks around the whole message, or attributions to famous people.
- Nothing preachy, religious, political, medical or financial. No names, phone numbers, emails or links.
- Between 40 and 300 characters each. Vary length, tone and topic; no two should open the same way.

For tone only, here are messages already in the river (do not repeat or paraphrase them):
{examples}"""


class Batch(BaseModel):
    messages: list[str]


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    existing = parse(SEEDS_FILE.read_text(encoding="utf-8"))
    client = anthropic.Anthropic()
    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=16000,
            messages=[{
                "role": "user",
                "content": PROMPT.format(count=count, examples="\n".join(f"- {t}" for t in existing)),
            }],
            output_format=Batch,
        )
    except anthropic.AuthenticationError:
        sys.exit("No valid Anthropic credentials: set ANTHROPIC_API_KEY or run `ant auth login`.")
    except anthropic.RateLimitError:
        sys.exit("Rate limited by the Anthropic API; try again in a minute.")
    except anthropic.APIConnectionError:
        sys.exit("Couldn't reach the Anthropic API.")
    except anthropic.APIStatusError as e:
        sys.exit(f"Anthropic API error {e.status_code}: {e.message}")

    if response.stop_reason == "refusal":
        sys.exit(f"The model declined: {response.stop_details}")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        sys.exit("The response was cut off; ask for fewer messages.")

    seen = set(existing)
    kept, dropped = [], []
    for text in (" ".join(m.split()) for m in response.parsed_output.messages):
        if text in seen:
            continue
        seen.add(text)
        (dropped if problems([text]) else kept).append(text)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        "# Candidates from " + MODEL + ". Review each one; copy the keepers into app/seeds.txt.\n\n"
        + "\n\n".join(kept) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(kept)} candidates to {OUT} ({len(dropped)} dropped by length or filter checks).")
    u = response.usage
    print(f"Tokens: {u.input_tokens} in, {u.output_tokens} out.")


if __name__ == "__main__":
    main()
