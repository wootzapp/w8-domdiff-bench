# DOM-Native Verifier Refactor

- Preserve Microsoft scoring, rubric, relevance, top-K, retry, penalty, validity, outcome, and failure behavior.
- Keep every current LLM-facing instruction and strictness rule byte-for-byte unchanged.
- Store DOM-oriented prompts directly in source; remove runtime terminology conversion.
- Use DOM-state names for evidence functions, schemas, logs, configuration, and result fields.
- Remove unused image-only hooks from the standalone DOM package.
- Keep the DOM verifier runtime-independent from the Microsoft verifier package.
- Let the audit reader accept both legacy screenshot results and DOM-native results.
- Verify prompt hashes, import isolation, package manifests, and all offline tests. No paid calls.
