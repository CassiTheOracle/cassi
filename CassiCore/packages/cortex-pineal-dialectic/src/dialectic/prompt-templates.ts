/**
 * Dialectic JSON Schemas — Output format declarations for Yang, Yin, and Serenity.
 *
 * Identity and operational context now live in posture-store.ts and are composed
 * via composeSystemPrompt('yang'|'yin'|'unity', 'dialectic'). This file is the
 * surviving home for the structured-output schemas the LLM is asked to produce.
 *
 * Signal types (unified across all prompts):
 *   edge_case | alternative | assumption | connection |
 *   contradiction | convergence | tension | gap
 */


export const YANG_SCHEMA = `{
  "branches": [
    {
      "id": "yang-1",
      "type": "alternative_interpretation|edge_case|cross_domain|what_if|assumption_challenge",
      "content": "2-4 sentences",
      "confidence": 0.0-1.0,
      "noveltyScore": 0.0-1.0
    }
  ]
}`;

export const YIN_CRITIQUE_SCHEMA = `{
  "critiques": [
    {
      "yangBranchId": "yang-1",
      "essence": "Core insight in 1 sentence (required when action is surface or compress)",
      "critique": "Reasoning for verdict",
      "relevance": 0.0-1.0,
      "action": "surface|compress|discard"
    }
  ]
}`;

export const YIN_BASELINE_SCHEMA = `{
  "baselineBranches": [
    {
      "id": "yin-1",
      "type": "grounding|constraint|reality_check|prioritization|risk_assessment",
      "content": "2-4 sentences",
      "confidence": 0.0-1.0,
      "relevanceScore": 0.0-1.0
    }
  ]
}`;

export const SERENITY_SCHEMA = `{
  "hasSignal": true,
  "signal": {
    "type": "edge_case|alternative|assumption|connection|contradiction|convergence|tension|gap",
    "content": "What the AI should do differently or consider. 1-2 sentences of guidance, not a user description",
    "confidence": 0.0-1.0,
    "urgency": "immediate|background"
  },
  "branchesConsidered": 0,
  "branchesSurfaced": 1
}`;

export const JSON_INSTRUCTION = 'Return ONLY valid JSON. No markdown fences, no explanation, no extra text.';
