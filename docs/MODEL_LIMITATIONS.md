# Model limitations and the Bible-only requirement

## What strict corpus mode can honestly guarantee

- Retrieval evidence comes only from approved corpus records.
- Every displayed quotation carries a source ID and corpus version.
- The prompt forbids external facts as biblical proof.
- The output must match a structured schema.
- The platform can reject unsupported citations and rerun analysis.

## What it cannot guarantee with a hosted general-purpose model

A general model’s weights already encode broad human language and knowledge. A prompt cannot erase that training history. Therefore `ARCHANGEL_STRICT_CORPUS_ONLY=true` means **strict evidence and output governance**, not Bible-only weights.

## Literal compliance path

1. Choose open-weight architecture and tokenizer.
2. Construct an approved dataset registry before training.
3. Include only texts whose use permits the exact training operation.
4. Preserve checksums, versions, licenses, transformations, and attribution.
5. Decide whether human language competence requires nonbiblical grammar data. If the answer is yes, the final model is no longer literally Bible-only; disclose that rather than redefining the requirement.
6. Train from scratch or start from weights whose training corpus meets the same policy.
7. Keep community data outside training unless it is explicitly consented, aligned, non-sensitive, and human-approved.
8. Evaluate against hallucinated verses, proof-texting, coercion, sectarian collapse, false prophecy, and unsafe referrals.
9. Publish a model card and dataset card with known gaps.

A model trained only on the biblical corpus may lack enough modern language, software, moderation, and safety competence for a public platform. The safer architecture may keep the **biblical authority model** separate from a non-authoritative safety and language-processing layer, with complete disclosure about what each layer was trained on.
