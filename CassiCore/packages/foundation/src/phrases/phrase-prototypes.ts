import type { PhrasePrototypeSet } from './mnemic-field/edge-relators.js'

export const SPAWN_EVALUATION_PHRASES: PhrasePrototypeSet = {
  phrases: {
    duplicate_work: [
      'this is the same task already assigned to an existing branch',
      'someone else is already working on this exact problem',
      'duplicating effort that is currently in progress elsewhere',
      'the goal is substantively identical to an active branch',
      'the work would reproduce results that another branch is creating',
    ],
    natural_subtask: [
      'this is a natural decomposition of the parent task',
      'the goal represents a well-scoped sub-problem of the current work',
      'extracting this as a child task follows from the parent plan',
      'the work is a clearly-contained component of the broader goal',
      'this straightforwardly breaks down into this piece',
    ],
    out_of_scope: [
      'the goal is unrelated to the constellation project scope',
      'this addresses a concern completely outside the defined task',
      'the work belongs in a separate project or constellation',
      'the goal is orthogonal to what the constellation was asked to do',
      'this would expand the project beyond its intended boundaries',
    ],
    high_dependency: [
      'every other branch is blocked waiting for this work',
      'the entire constellation depends on this completing first',
      'this is a critical path item that everything else builds on',
      'failure here would cascade to all sibling branches',
      'the output is a prerequisite for the rest of the project',
    ],
  },
  labels: ['duplicate_work', 'natural_subtask', 'out_of_scope', 'high_dependency'],
}

export const WORK_UNIT_ANNOTATION_PHRASES: PhrasePrototypeSet = {
  phrases: {
    implementation: [
      'completed the implementation of the feature as specified',
      'created the new file with all the required functionality',
      'added the function to handle the described behavior',
      'implemented the change and verified it compiles',
      'finished writing the production code for this task',
    ],
    exploration: [
      'reading through the codebase to understand the architecture',
      'investigating the existing code to determine where to make changes',
      'searching for the right files and patterns to follow',
      'looking at how similar features were implemented previously',
      'browsing the source code to build a mental model',
    ],
    research: [
      'studied the architectural patterns used across the system',
      'compared multiple alternative approaches before deciding',
      'benchmarked the options and selected the best fit',
      'traced the full execution flow through all relevant modules',
      'conducted deep investigation into the subsystem design',
    ],
    testing: [
      'ran the test suite to verify the changes pass',
      'wrote new tests to cover the modified behavior',
      'verified the fix by running the failing test case',
      'validated the output matches the expected result',
      'all tests pass after the latest modifications',
    ],
    revision: [
      'fixed the bug found during the code review',
      'addressed the feedback from the reviewer analysis',
      'corrected the issue that the reviewer identified',
      'changed the implementation to handle the edge case',
      'updated the code based on the review comments',
    ],
    drift: [
      'started working on something unrelated to the assigned task',
      'explored a tangent that does not advance the goal',
      'got distracted by an interesting but irrelevant side issue',
      'the investigation went down a path unrelated to the objective',
      'the activity does not contribute to the stated deliverables',
    ],
  },
  labels: ['implementation', 'exploration', 'research', 'testing', 'revision', 'drift'],
}

export const DRIFT_TYPE_PHRASES: PhrasePrototypeSet = {
  phrases: {
    scope_creep: [
      'expanding to adjacent concerns not in the original scope',
      'broadening the task to include enhancements beyond the goal',
      'taking on extra features that were not requested',
      'the scope grew beyond what was originally defined',
    ],
    too_deep: [
      'diving too deep into implementation details of a dependency',
      'lost in the internals of a library rather than the task itself',
      'spending excessive time understanding code that is not relevant',
      'going deeper into the subsystem than the task requires',
    ],
    genuinely_lost: [
      'confused about what the task is actually asking for',
      'uncertain about which direction to take the implementation',
      'spinning because the goal statement is ambiguous',
      'working on things that do not move the needle',
    ],
    useful_tangent: [
      'investigating something adjacent that will pay off later',
      'building foundational understanding that enables the next step',
      'exploring related code that provides important context',
      'the detour is productive even if not on the critical path',
    ],
  },
  labels: ['scope_creep', 'too_deep', 'genuinely_lost', 'useful_tangent'],
}

export const DIALECTIC_TYPE_PHRASES: PhrasePrototypeSet = {
  phrases: {
    finding: [
      'discovered that the codebase architecture has this property',
      'found evidence that supports a particular design decision',
      'investigation revealed important structural information',
      'key insight emerged from the analysis of the subsystem',
      'our branch research shows that this pattern applies',
    ],
    challenge: [
      'this conflicts with what the other branch concluded',
      'the approach has a flaw that the other branch did not notice',
      'counterpoint to the finding that was previously shared',
      'alternative interpretation of the evidence suggests otherwise',
      'raises a concern about the validity of the conclusion',
    ],
    concession: [
      'you are right about the issue that was raised',
      'accept the critique and acknowledge the mistake',
      'withdraw the earlier claim in light of the new evidence',
      'revised understanding after considering the challenge',
      'concede the point and adjust the approach accordingly',
    ],
  },
  labels: ['finding', 'challenge', 'concession'],
}

export const DIALECTIC_QUALITY_PHRASES: PhrasePrototypeSet = {
  phrases: {
    genuine_tension: [
      'a fundamental disagreement about the correct design approach',
      'an irreconcilable difference in architectural philosophy',
      'both sides have valid but contradictory positions',
      'the disagreement touches core assumptions that are incompatible',
    ],
    surface_agreement: [
      'agree at a surface level but have different underlying assumptions',
      'seem aligned but diverge on the crucial implementation details',
      'superficially consistent while hiding deeper disagreement',
      'the apparent consensus masks a significant conceptual difference',
    ],
  },
  labels: ['genuine_tension', 'surface_agreement'],
}

export const EPISTEMIC_SHIFT_PHRASES: PhrasePrototypeSet = {
  phrases: {
    reversal: [
      'this changes my understanding of how the system works',
      'reverses the earlier conclusion that was drawn',
      'I was wrong about the approach and need to correct it',
      'overturns the previous assumption about the architecture',
      'contradicts what I previously thought was the right answer',
    ],
    resolution: [
      'resolves the open question that has been blocking progress',
      'answers the earlier concern about the design decision',
      'finally explains why the behavior was inconsistent',
      'the missing piece that ties everything together is now clear',
      'this finding closes the investigation that was in progress',
    ],
    revelation: [
      'reveals a hidden assumption that was driving the wrong approach',
      'never considered this perspective and it changes everything',
      'fundamentally shifts the approach to the entire problem',
      'uncovers a structural issue that was invisible before',
      'exposes a gap in the mental model that explains prior confusion',
    ],
    confirmation: [
      'confirms the earlier suspicion about the root cause',
      'validates the approach that was taken and justifies the path',
      'provides strong evidence that supports the working hypothesis',
      'proves that the design assumption was correct all along',
      'corroborates the finding with independent supporting data',
    ],
  },
  labels: ['reversal', 'resolution', 'revelation', 'confirmation'],
}

export const REVERIE_HAS_INSIGHT_PHRASES: PhrasePrototypeSet = {
  phrases: {
    has_insight: [
      'this reasoning contains an important observation that needs attention',
      'there is a notable pattern in how the approach is reasoned about',
      'the logic here reveals something surprising about the problem',
      'a key assumption or contradiction is visible in this reasoning',
      'something in this analysis deserves deeper investigation',
    ],
    no_insight: [
      'the reasoning is straightforward and contains no surprises',
      'this is a routine step with no notable observations to surface',
      'nothing in this analysis raises new questions or concerns',
      'the logic follows the expected path without any deviation',
      'standard reasoning that does not need further examination',
    ],
  },
  labels: ['has_insight', 'no_insight'],
}

export const COHERENCE_MISMATCH_PHRASES: PhrasePrototypeSet = {
  phrases: {
    gradual_drift: [
      'slowly diverged over time due to independent updates',
      'accumulated small differences that eventually became significant',
      'drifted apart organically without any single triggering event',
      'the gap grew gradually through many small independent changes',
    ],
    fundamental_disagreement: [
      'the two modules encode fundamentally contradictory information',
      'the representations are incompatible at a conceptual level',
      'the disagreement reflects different underlying assumptions',
      'the modules were updated with conflicting conclusions',
    ],
    out_of_sync_latency: [
      'one module was updated but the change has not propagated yet',
      'the update was applied to one system but not the other',
      'a timing issue where the faster module raced ahead',
      'the data is correct but has not yet been synchronized',
    ],
    scope_difference: [
      'each module captures a different subset of the same concept',
      'the representations overlap partially but cover different aspects',
      'one module has a broader scope than the other for the same topic',
      'the modules agree on the core but diverge on peripheral details',
    ],
  },
  labels: ['gradual_drift', 'fundamental_disagreement', 'out_of_sync_latency', 'scope_difference'],
}

export const DEVIATION_REASON_PHRASES: PhrasePrototypeSet = {
  phrases: {
    under_scoped: [
      'the task turned out to be much larger than the original estimate',
      'more complexity emerged than was visible during planning',
      'required several additional subtasks to complete properly',
      'hidden complexity surfaced once work began in earnest',
      'the scope expanded significantly during implementation',
    ],
    hidden_dependency: [
      'depended on work that had not been completed yet',
      'needed output from another task that was behind schedule',
      'a prerequisite dependency was not ready when work started',
      'blocked on an external task that was not accounted for',
    ],
    too_granular: [
      'the task was too fine-grained to be useful as a separate unit',
      'overly decomposed into pieces that were too small to track',
      'trivial enough that it should have been combined with another',
      'the decomposition was unnecessarily detailed for this level',
    ],
    wrong_abstraction: [
      'decomposed along the wrong axis or at the wrong level',
      'should have been defined at a higher level of abstraction',
      'the split of concerns did not match the actual work structure',
      'the task boundaries cut across natural implementation units',
    ],
    context_shift: [
      'the goal changed mid-execution due to new information',
      'stakeholder priorities shifted while the task was in progress',
      'new requirements emerged that altered the original plan',
      'the direction changed in response to findings from other work',
    ],
  },
  labels: ['under_scoped', 'hidden_dependency', 'too_granular', 'wrong_abstraction', 'context_shift'],
}

export const CORPUS_BRANCH_RELATION_PHRASES: PhrasePrototypeSet = {
  phrases: {
    semantic_redundancy: [
      'both branches are solving the same underlying problem',
      'the two efforts are duplicating work on the same concern',
      'reimplementing something that the other branch already handles',
      'two independent approaches converging on the same solution',
      'both branches are producing equivalent output for the same need',
    ],
    semantic_conflict: [
      'the changes from these branches will break each other at runtime',
      'incompatible design decisions that cannot coexist in the same codebase',
      'the two branches make contradictory assumptions about shared interfaces',
      'one branch work reverts or invalidates the other branch changes',
      'designs that cannot be reconciled without one side fundamentally changing',
    ],
    semantic_dependency: [
      'one branch depends on the output of the other to make progress',
      'needs to consume results from the sibling branch before continuing',
      'the downstream work is blocked waiting for the upstream to finish',
      'prerequisite for continuing is the completion of the other branch',
      'logical next step after the sibling completes its foundation work',
    ],
    convergence_opportunity: [
      'the insight from one branch generalizes to what the other is doing',
      'both branches are discovering the same solution pattern independently',
      'the work can be consolidated into a single approach or module',
      'a shared abstraction is emerging that would serve both branches',
      'the findings from both branches converge on a unified understanding',
    ],
  },
  labels: ['semantic_redundancy', 'semantic_conflict', 'semantic_dependency', 'convergence_opportunity'],
}

export const DIRECTIVE_QUALITY_PHRASES: PhrasePrototypeSet = {
  phrases: {
    actionable: [
      'take the following concrete step to improve the situation',
      'here is a specific action you can take right now',
      'modify the approach by doing this particular thing',
      'execute this explicit change to the current plan',
      'follow this precise instruction to correct the course',
    ],
    vague: [
      'generally try to improve the situation somehow',
      'the approach needs some kind of improvement',
      'consider making changes that might help',
      'be more careful and try to do better work',
      'think about whether there is a better way forward',
    ],
    contradictory: [
      'directs the branch to do something that conflicts with its current goal',
      'contradicts the earlier directive that was sent to this same branch',
      'tells the branch to change direction but the reason is unclear',
      'the instruction is internally inconsistent with itself',
      'recommends an approach that is incompatible with the branch tools',
    ],
  },
  labels: ['actionable', 'vague', 'contradictory'],
}

export const SIGNAL_TYPE_PHRASES: PhrasePrototypeSet = {
  phrases: {
    concern: [
      'something about this situation is worrying and needs attention',
      'there is a risk here that could cause problems later',
      'this pattern suggests a potential failure mode',
      'the current approach has a vulnerability that should be addressed',
      'a problem is developing that needs intervention',
    ],
    anomaly: [
      'something unexpected happened that should not have occurred',
      'the behavior deviates from what was expected or predicted',
      'a result contradicts the established pattern or assumption',
      'an error or inconsistency appeared that does not fit the model',
      'a surprising outcome occurred that requires investigation',
    ],
    insight: [
      'a new understanding emerged that changes the mental model',
      'connected two previously separate concepts in a useful way',
      'discovered a pattern or principle that was not visible before',
      'the analysis revealed something important and non-obvious',
      'a realization occurred that advances the understanding',
    ],
    decision: [
      'chose a specific course of action from among alternatives',
      'made a commitment to a particular approach or design',
      'selected one option and dismissed the other possibilities',
      'resolved an open question with a definitive answer',
      'finalized the direction and will now execute on it',
    ],
  },
  labels: ['concern', 'anomaly', 'insight', 'decision'],
}

export const MEMORY_WORTHINESS_PHRASES: PhrasePrototypeSet = {
  phrases: {
    worth_remembering: [
      // --- USER: Decisions and preferences ---
      'the user made a decision about which approach to take',
      'the user expressed a preference for how something should be done',
      'the user chose one option over another',
      'the user rejected a suggestion and explained why',
      'the user specified a requirement or constraint they care about',

      // --- USER: Corrections and lessons ---
      'the user corrected a misunderstanding about how things work',
      'the user pointed out a mistake in my reasoning',
      'the user explained why the system is actually different from what I assumed',
      'the user clarified something I got wrong',
      'the user corrected my terminology or framing',

      // --- USER: Architecture and design ---
      'the user described how the system architecture works',
      'the user explained the design rationale behind a component',
      'the user shared technical constraints that affect implementation choices',
      'the user provided context about how the project is structured',
      'the user drew a comparison between two technical approaches',

      // --- USER: Setup and environment ---
      'the user revealed a configuration detail about their environment',
      'the user shared what tools they use and how they work',
      'the user described their development workflow',
      'the user specified which services or dependencies they rely on',
      'the user shared their directory structure or project layout',

      // --- USER: Discoveries and insights ---
      'a non-obvious root cause was identified for a problem',
      'an important discovery was made about how something actually works',
      'a bug or issue was diagnosed and the fix was non-trivial',
      'a pattern or relationship was uncovered that explains prior confusion',

      // --- USER: Goals and intent ---
      'the user stated what they want to achieve in this project',
      'the user described the larger goal that this work serves',
      'the user prioritized one task or requirement over another',
      'the user specified acceptance criteria or quality standards',

      // --- USER: Feedback and evaluation ---
      'the user evaluated a proposed approach as good or bad',
      'the user shared their opinion on the quality of work produced',
      'the user indicated what they value in the implementation',
      'the user expressed satisfaction or dissatisfaction with a result',

      // --- USER: Personal context ---
      'the user mentioned their role or relationship to the project',
      'the user shared something about their background or expertise',
      'the user explained their naming conventions or coding style',
      'the user described how they think about organizing the code',

      // --- USER: Important caveats ---
      'the user warned about a common pitfall or footgun',
      'the user flagged something as dangerous or destructive',
      'the user recommended against a particular approach',
      'the user shared tribal knowledge that is not documented anywhere',

      // --- ASSISTANT: Synthesis and discovery (what was found) ---
      'a clear picture emerged of how the architecture fits together',
      'the investigation revealed how the component is actually wired',
      'the analysis produced a structured summary of the system internals',
      'the search uncovered the relevant code and its loading pattern',
      'the evidence shows that the system works differently than expected',
      'tracing the execution path revealed the full data flow',
      'the comparison between approaches showed clear tradeoffs',
      'a comprehensive synthesis of findings was produced',

      // --- ASSISTANT: Analysis and evaluation (what it means) ---
      'the key insight is how the components relate to each other',
      'this approach has a fundamental problem because of how it works',
      'the core issue is caused by an architectural constraint',
      'the recommended approach is better because it avoids a known pitfall',
      'the reasoning shows why one design is preferable over alternatives',
      'the evaluation identified strengths and weaknesses of each option',
      'the analysis connects previously separate concepts in a useful way',
      'a non-obvious consequence was discovered from the design choice',

      // --- ASSISTANT: Recommendations and decisions ---
      'a specific course of action was recommended with supporting rationale',
      'one option was eliminated based on evidence from the investigation',
      'the proposed solution addresses all the constraints the user specified',
      'the recommended change would affect these specific components',
      'a design decision was made and the tradeoffs were documented',
      'an implementation plan was outlined with concrete steps',

      // --- ASSISTANT: Self-correction and learning ---
      'the assistant realized it was wrong about a previous assumption',
      'the assistant revised its understanding based on new evidence',
      'the assistant acknowledged a mistake and corrected the record',
      'earlier conclusions were updated in light of contradictory findings',

      // --- ASSISTANT: Technical explanation ---
      'the architecture of the component was explained with its role',
      'the data flow through the system was traced end to end',
      'the relationship between modules was described in detail',
      'how the protocol or API works was explained step by step',
      'the configuration options and their effects were documented',
      'the build or deployment process was explained with important details',

      // --- ASSISTANT: Patterns and principles ---
      'a reusable pattern was identified that applies to similar situations',
      'a general principle was extracted from the specific case',
      'the approach generalizes to other parts of the system',
      'a convention or standard practice was established for future work',

      // --- ASSISTANT: Thinking and reasoning (valuable cognitive content) ---
      'careful consideration of the tradeoffs led to a clear recommendation',
      'working through the problem step by step revealed the right approach',
      'reconsidering the initial assumption changed the direction entirely',
      'connecting the dots between separate findings produced a coherent picture',
      'the reasoning process identified a flaw that was not obvious at first',
      'examining the evidence from multiple angles confirmed the hypothesis',
      'the thinking shows a progression from confusion to clear understanding',
      'weighing the pros and cons systematically eliminated weaker options',
    ],

    noise: [
      // --- Tool results (belt and suspenders with role filter) ---
      'this is the output of a shell command that was just run',
      'here are the contents of a file that was read from disk',
      'this is the result of a search query across files',
      'this is a list of files in a directory',

      // --- User: Trivial responses ---
      'a simple acknowledgement like okay sure or got it',
      'a brief greeting or farewell',
      'an affirmative one-word response',
      'a generic thank you exchange',
      'a single word or short phrase with no substantive content',

      // --- User: Status updates with no lasting value ---
      'the build completed successfully or failed',
      'the tests are running or have finished',
      'a process started or stopped',
      'an installation completed',

      // --- Assistant: Planning what to do next (not analysis) ---
      'let me search for something in the codebase to find the answer',
      'let me read a file to understand how it is implemented',
      'let me check what the config says about a setting',
      'i need to locate where this feature is defined in the code',
      'let me explore different directories until I find the right file',
      'let me look at this specific function or method',
      'let me run a command to verify the results',

      // --- Assistant: Transitional framing ---
      'good question let me look into this and find the answer',
      'found the relevant code let me explain what it does',
      'now let me examine this other file to understand the flow',
      'let me dig deeper into this specific component',
      'let me check the results of what was just discovered',
      'let me verify this by checking the actual implementation',
      'let me trace through the code step by step',

      // --- Assistant: Tool-operation framing ---
      'let me search more specifically using different terms',
      'let me broaden the search to find more results',
      'let me check another location for the relevant files',
      'let me look at the broader directory structure',
      'now let me check this other part of the codebase',
      'let me now check the actual value in the code',

      // --- Assistant: Near-empty or pure-tool responses ---
      'a response that is empty or contains only tool call output',
      'a message that only delegates to external tools with no synthesis',

      // --- Assistant: Thinking about what to search next ---
      'i should look at the relevant source files to understand the code',
      'let me find where this particular feature is implemented',
      'i need to trace through the execution path to find the bug',
      'let me check the test files for examples of correct usage',
      'i should read the documentation to understand the API',
    ],
  },
  labels: ['worth_remembering', 'noise'],
}

/** Prototypes for what makes a retrieved engram actively useful in a task. */
export const RETRIEVAL_RELEVANCE_PHRASES: PhrasePrototypeSet = {
  phrases: {
    directly_applied: [
      'the retrieved information was directly used in the next action',
      'the primary acted on this memory to make a decision',
      'the content was copied or referenced in a tool call argument',
      'the engram provided a fact that changed what happened next',
    ],
    contextually_relevant: [
      'the retrieved information provided useful background context',
      'the engram confirmed or reinforced the correct approach',
      'the memory reminded the assistant of a constraint or preference',
      'the content helped narrow the search space or eliminate options',
    ],
    not_useful: [
      'the retrieved information was not relevant to the current task',
      'the engram described a different problem or domain entirely',
      'the content was factually wrong or misleading',
      'the memory was about a resolved issue that no longer applies',
    ],
  },
  labels: ['directly_applied', 'contextually_relevant', 'not_useful'],
}
