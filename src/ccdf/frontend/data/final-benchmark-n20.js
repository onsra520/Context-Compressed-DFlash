export const mockResults = {
    isMock: true,
    throughput: {
        gsm8k: [
            { name: "Baseline-AR", value: 31.0 },
            { name: "DFlash-R1", value: 113.7 },
            { name: "LLMLingua-AR-R2", value: 30.5 },
            { name: "CC-DFlash-R2", value: 100.9 }
        ],
        qmsum: [
            { name: "Baseline-AR", value: 24.0 },
            { name: "DFlash-R1", value: 41.6 },
            { name: "LLMLingua-AR-R2", value: 23.5 },
            { name: "CC-DFlash-R2", value: 41.2 }
        ]
    },
    tokenReduction: {
        gsm8k: {
            oldPrompt: 199,
            v5Prompt: 163,
            afterSafeguard: 161,
            promptCleanupPct: -18,
            llmlinguaReductionPct: -1.3
        },
        qmsum: {
            fullTranscript: 12142,
            selectedContext: 922,
            compressedContext: 844,
            selectionReductionPct: 92.4,
            llmlinguaReductionPct: 8.5,
            overallReductionPct: 93.0
        }
    },
    quality: {
        gsm8k: [
            { name: "Baseline-AR", value: 18, total: 20 },
            { name: "DFlash-R1", value: 18, total: 20 },
            { name: "LLMLingua-AR-R2", value: 18, total: 20 },
            { name: "CC-DFlash-R2", value: 18, total: 20 }
        ],
        qmsum: [
            { name: "Baseline-AR", value: 0.178 },
            { name: "DFlash-R1", value: 0.180 },
            { name: "LLMLingua-AR-R2", value: 0.179 },
            { name: "CC-DFlash-R2", value: 0.178 }
        ]
    },
    latency: {
        gsm8k: {
            dflash: {
                compression: 0,
                prefill: 87,
                generation: 968,
                total: 1055
            },
            ccdflash: {
                compression: 92,
                prefill: 84,
                generation: 1008,
                total: 1184
            },
            deltaMs: 129,
            deltaPct: 12.2
        },
        qmsum: {
            dflash: {
                compression: 0,
                generationPipeline: 2057,
                total: 2057
            },
            ccdflash: {
                compression: 466,
                generationPipeline: 1954,
                total: 2420
            },
            deltaMs: 363,
            deltaPct: 17.6
        }
    },
    kpi: {
        vram: "3.63 GiB",
        acceptanceLength: "5.0",
        compressionFallback: "0%",
        parserFailures: 0,
        emptyOutputs: 0
    }
};
