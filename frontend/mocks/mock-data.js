export const architectureSteps = [
    {
        title: 'Original prompt enters the pipeline',
        description: 'The input contains a long context block and a protected question.',
        stage: 'Input',
        node: 'nInput',
        edge: null,
        packet: 'prompt',
        context: '1,240 input tokens',
        payload: ['context', 'question'],
        result: ['raw prompt'],
        log: 'Received original context and question.'
    },
    {
        title: 'Separate context from the question',
        description: 'Only the context is compressible. The question and answer instruction remain protected.',
        stage: 'Segment',
        node: 'nSplit',
        edge: 'eInputSplit',
        packet: 'split',
        context: 'Context: 1,198 · Question: 42',
        payload: ['context', 'question'],
        result: ['2 protected segments'],
        log: 'Segmenter isolated the compressible context.'
    },
    {
        title: 'Compress the context',
        description: 'LLMLingua-2 selects answer-relevant text and reduces the context token count.',
        stage: 'Compress',
        node: 'nCompress',
        edge: 'eSplitCompress',
        packet: 'context',
        context: '1,198 → 628 context tokens',
        payload: ['keep 52%', 'extractive'],
        result: ['570 tokens removed'],
        log: 'Context compression completed with a 52% keep rate.'
    },
    {
        title: 'Protect the question',
        description: 'The original question and final-answer instruction bypass compression unchanged.',
        stage: 'Protect',
        node: 'nProtect',
        edge: 'eSplitProtect',
        packet: 'question',
        context: '42 protected tokens',
        payload: ['question', 'instruction'],
        result: ['preserved'],
        log: 'Protected suffix verified before prompt assembly.'
    },
    {
        title: 'Assemble the final compressed prompt',
        description: 'Compressed context and protected question are merged into natural text.',
        stage: 'Assemble',
        node: 'nMerge',
        edge: 'eCompressMerge',
        secondaryEdge: 'eProtectMerge',
        packet: 'final prompt',
        context: '670 effective input tokens',
        payload: ['628 context', '42 question'],
        result: ['natural text'],
        log: 'Final compressed prompt assembled.'
    },
    {
        title: 'Run target prefill',
        description: 'The quantized target processes the shorter prompt and creates the initial cache state.',
        stage: 'Prefill',
        node: 'nPrefill',
        edge: 'eMergePrefill',
        packet: '670 tokens',
        context: 'Prefill on compressed input',
        payload: ['target cache'],
        result: ['shorter prefill'],
        log: 'Target prefill completed on the compressed prompt.'
    },
    {
        title: 'Draft a candidate token block',
        description: 'DFlash proposes multiple candidate tokens from the current accepted context.',
        stage: 'Draft',
        node: 'nDraft',
        edge: 'ePrefillDraft',
        packet: 'draft block',
        context: 'Current accepted context',
        payload: ['the', 'answer', 'is', '42'],
        result: ['4 candidates'],
        log: 'DFlash produced a candidate block.'
    },
    {
        title: 'Verify with the target model',
        description: 'The target accepts a prefix and rejects the first mismatching candidate.',
        stage: 'Verify',
        node: 'nVerify',
        edge: 'eDraftVerify',
        packet: 'verify',
        context: 'Target remains final authority',
        payload: ['✓ the', '✓ answer', '✓ is', '✓ 42'],
        result: ['4 accepted'],
        log: 'Target verification accepted the full draft block.'
    },
    {
        title: 'Accumulate in buffer',
        description: 'Accepted tokens are pushed to the output buffer. Generation loops back to draft if incomplete.',
        stage: 'Buffer',
        node: 'nBuffer',
        edge: 'eVerifyBuffer',
        secondaryEdge: 'eBufferLoop',
        packet: 'accepted',
        context: 'Accumulating tokens',
        payload: ['Final', 'answer:', '42'],
        result: ['buffered'],
        log: 'Tokens buffered, loop triggered.'
    },
    {
        title: 'Return final output',
        description: 'Generation is complete. The terminal output is returned to the user.',
        stage: 'Final',
        node: 'nFinal',
        edge: 'eBufferFinal',
        packet: 'completion',
        context: 'Generation complete',
        payload: ['Final', 'answer:', '42'],
        result: ['terminal output'],
        log: 'Generation finished, final output ready.'
    }
];

export const demoPresets = {
    gsm8k: {
        label: 'GSM8K · short numeric prompt',
        prompt: `Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?\n\nReturn the result on the final line using: Final answer: <number>`
    },
    qmsum: {
        label: 'QMSum · long meeting context',
        prompt: `Meeting transcript:\n\nAlice: We need to decide how the mobile release should handle offline synchronization. The current build retries every ten seconds, but this causes duplicate uploads when the connection is unstable.\n\nBob: The backend team can add idempotency keys, although that will not land before the next release candidate. For the short term, the client could queue changes locally and retry only after the network state has been stable for thirty seconds.\n\nCarla: Product wants the release this Friday. We can accept a limited offline mode if the interface clearly shows which records are pending. We should not silently discard edits.\n\nAlice: Then the proposal is to keep local changes, display a pending badge, wait for a stable connection, and retry. Duplicate protection will be added on the server in the following sprint.\n\nBob: I agree, but analytics events should not be queued with business records. They can be dropped if the app is closed.\n\nCarla: Please document that distinction in the release notes and create a follow-up ticket for server-side idempotency.\n\nQuestion: What decision did the team make about offline synchronization for the upcoming release, and what work was deferred?`
    },
    custom: {
        label: 'Custom prompt',
        prompt: 'Explain why context compression can reduce prefill cost, and identify the main end-to-end trade-off.'
    }
};

export const metricDefs = [
    ['Original input tokens', 'Estimated tokens in the full prompt before any compression.'],
    ['Effective prefill tokens', 'Tokens actually processed during target prefill. Baseline-AR and D-Flash use the full input; CC-DFlash uses the compressed prompt.'],
    ['Compression ratio', 'Original input tokens divided by compressed input tokens. Only applies to CC-DFlash.'],
    ['Compression overhead', 'CPU time spent compressing the context before model inference.'],
    ['Prefill latency', 'Time required for the target model to process the input prompt and initialize the cache.'],
    ['Generation latency', 'Time spent generating output tokens after prefill.'],
    ['End-to-end latency', 'Compression overhead + prefill + generation. This is the conservative comparison metric.'],
    ['Generation throughput', 'Output tokens divided by generation latency. It does not include compression or prefill.'],
    ['Acceptance length τ', 'Average number of draft tokens accepted per DFlash verification step. Not applicable to Baseline-AR.'],
    ['Numeric quality proxy', 'GSM8K uses final numeric answer matching as a deterministic quality signal.'],
    ['Lexical overlap proxy', 'QMSum uses normalized overlap as diagnostic evidence, not semantic correctness.'],
    ['Workload class', 'Short, medium, or long context. Compression becomes more useful as prefill savings can offset its overhead.']
];
