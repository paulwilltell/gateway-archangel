# Safety boundary

The safety classifier runs before theological analysis and its result is re-applied after any model output. A model cannot downgrade it.

US defaults:

- Immediate danger or medical emergency: `911`.
- Suicidal or emotional crisis: call or text `988`; immediate danger still routes to `911`.
- Suspected poisoning: Poison Control `1-800-222-1222`; collapse, seizure, breathing failure, or inability to awaken routes to `911`.

The numbers are configuration values because international deployments require local services.

The system must not provide a verse as a substitute for emergency response, medicine, crisis support, legal representation, or other licensed professional care. It should also avoid flooding ordinary theological discussion with crisis notices; thresholds must be evaluated continually against false positives and false negatives.
