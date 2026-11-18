# AI development record

The development was performed with Codex in the user’s existing chat session. The exact initial prompt is in `INITIAL_PROMPT.md`.

Codex records token-count events in the local session log. Below are two actual snapshots from the AI coding session after implementation and verification. The baseline was captured immediately before the first source file was written. A later deployment step, if one happens, is outside this measured interval.

| Counter | Baseline at 16:38:07 UTC | Snapshot at 16:49:29 UTC | Delta |
|---|---:|---:|---:|
| Input tokens, including cached context | 623,929,699 | 628,131,997 | 4,202,298 |
| Cached input tokens | 608,341,504 | 612,416,256 | 4,074,752 |
| New input tokens | 15,588,195 | 15,715,741 | 127,546 |
| Output tokens | 1,254,314 | 1,278,800 | 24,486 |
| Total tokens | 625,184,013 | 629,410,797 | 4,226,784 |

The development happened in an existing, unusually long conversation. Repeated cached conversation context dominates the total input count. The material created for this prototype is represented more usefully by 127,546 new input and 24,486 output tokens. These values are direct deltas from the Codex `token_count` events, not estimates based on file size. The full session log is not included because it contains private conversation data.
