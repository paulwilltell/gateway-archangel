# Data governance

## Training is opt-in and non-automatic

The platform separates:

1. permission to display a public post;
2. permission to analyze it for the immediate community feature;
3. permission to copy it into a future research candidate set;
4. human approval for a specific training or evaluation use.

These are not the same consent.

## Current gate

A contribution is excluded from the candidate table when any of the following is true:

- no explicit research consent;
- private or unpublished content;
- safety-sensitive content;
- detected email, phone number, government identifier, or street address;
- alignment is anything other than `aligned`;
- analysis confidence is below the configured threshold;
- training mode is off.

Passing the gate creates only `pending_theological_review`. It does not update a model.

## Production requirements

- Revocable consent and a user-facing training history.
- Dataset lineage from post → candidate → export → training run → model version.
- Separate retention periods for community content, security logs, and rejected candidates.
- Encryption at rest and in transit.
- Least-privilege moderator access.
- No private journal or direct-message training by default.
- Special handling or total exclusion for minors, abuse disclosures, health information, sexual content, legal matters, financial identifiers, and crisis material.
- A documented process for removing data from future datasets and deprecating affected model versions.
