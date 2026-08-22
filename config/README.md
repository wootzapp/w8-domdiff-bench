# Endpoint configuration

`endpoints/openai/canonical/` contains the non-secret OpenAI endpoint definitions
used by both verifier modes. Credentials are read only from `OPENAI_API_KEY` or
the benchmark `.env` file and must never be placed in these JSON files.

The controlled comparison requires exactly `gpt-5.2` for rubric/evidence
judgment and `o4-mini` for action and validity judgment.
