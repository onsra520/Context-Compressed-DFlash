const fs = require('fs');

// 1. Modifying mock-data.js
let mockData = fs.readFileSync('mocks/mock-data.js', 'utf-8');

// Find the export array
const arrayStart = mockData.indexOf('export const architectureSteps = [');
const arrayEndStr = '];\n\nexport const demoPresets';
const arrayEnd = mockData.indexOf(arrayEndStr);

let preStepsRaw = mockData.substring(arrayStart, arrayEnd + 2);

// We will parse the array and replace it. But to be safe, we can just replace the file contents.
// Instead of parsing, I will just construct the new file content.
let newMockData = `export const architectureSteps = [
    {
        title: 'Original prompt enters the pipeline',
        description: 'The input contains a long context block and a protected question.',
        stage: 'Input',
        node: 'nInput',
        activeEdge: null,
        packet: 'prompt',
        context: '1,240 input tokens',
        process: 'Initial state',
        output: 'Raw prompt ready',
        log: 'Received original context and question.'
    },
    {
        title: 'Separate context from the question',
        description: 'Only the context is compressible. The question and answer instruction remain protected.',
        stage: 'Segment',
        node: 'nSplit',
        activeEdge: 'original-to-context-compression',
        packet: 'split',
        context: 'Context: 1,198 · Question: 42',
        process: 'Segmenting input',
        output: '2 protected segments',
        log: 'Segmenter isolated the compressible context.'
    },
    {
        title: 'Compress the context',
        description: 'LLMLingua-2 selects answer-relevant text and reduces the context token count.',
        stage: 'Compress',
        node: 'nCompress',
        activeEdge: 'segmenter-to-llmlingua',
        packet: 'context',
        context: '1,198 → 628 context tokens',
        process: 'Extractive compression (CPU)',
        output: '570 tokens removed',
        log: 'Context compression completed with a 52% keep rate.'
    },
    {
        title: 'Protect the question',
        description: 'The original question and final-answer instruction bypass compression unchanged.',
        stage: 'Protect',
        node: 'nProtect',
        activeEdge: 'segmenter-to-protected-question',
        packet: 'question',
        context: '42 protected tokens',
        process: 'Bypass compression',
        output: 'Preserved',
        log: 'Protected suffix verified before prompt assembly.'
    },
    {
        title: 'Assemble the final compressed prompt',
        description: 'Compressed context and protected question are merged into natural text.',
        stage: 'Assemble',
        node: 'nMerge',
        activeEdge: 'context-compression-to-prompt-compression',
        packet: 'final prompt',
        context: '670 effective input tokens',
        process: 'Merge segments',
        output: 'Natural text prompt',
        log: 'Final compressed prompt assembled.'
    },
    {
        title: 'Run target prefill',
        description: 'The quantized target processes the shorter prompt and creates the initial cache state.',
        stage: 'Prefill',
        node: 'nPrefill',
        activeEdge: 'prompt-compression-to-target-prefill',
        packet: '670 tokens',
        context: 'Prefill on compressed input',
        process: 'Target prefill',
        output: 'Target cache state',
        log: 'Target prefill completed on the compressed prompt.'
    },
    {
        title: 'KHỞI TẠO D-FLASH',
        stage: 'D-FLASH · CYCLE 1 / 3',
        description: 'Target Prefill chuyển trạng thái context đã xử lý vào vòng sinh D-Flash.',
        node: 'nDraft',
        activeEdge: 'target-prefill-to-dflash-container',
        packet: 'prompt',
        context: 'Target cache từ prompt đã nén',
        process: 'Khởi tạo D-Flash generation state',
        output: 'Cycle 1 ready',
        log: 'Target Prefill đã chuyển trạng thái vào D-Flash Draft.',
        cycleBadge: 'CYCLE 1 / 3'
    },
    {
        title: 'DRAFT BLOCK ỨNG VIÊN',
        stage: 'DRAFT · CYCLE 1 / 3',
        description: 'Draft model đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.',
        node: 'nDraft',
        activeEdge: 'draft-to-verify',
        packet: 'draft block',
        context: 'Current accepted context',
        process: 'Draft 16 candidate tokens · Cycle 1 / 3',
        output: '16 candidate tokens',
        log: 'Draft model đã đề xuất block token thứ 1.',
        cycleBadge: 'CYCLE 1 / 3'
    },
    {
        title: 'TARGET KIỂM CHỨNG',
        stage: 'VERIFY · CYCLE 1 / 3',
        description: 'Mô hình đích kiểm chứng block ứng viên, chấp nhận prefix phù hợp và loại phần không khớp.',
        node: 'nVerify',
        activeEdge: 'verify-to-output-buffer',
        packet: 'verify',
        context: '16 candidate tokens',
        process: 'Target verification · Cycle 1 / 3',
        output: '11 accepted · 5 rejected',
        log: '11 token được commit vào Output Buffer.',
        cycleBadge: 'CYCLE 1 / 3'
    },
    {
        title: 'TIẾP TỤC VÒNG SINH',
        stage: 'LOOP · CYCLE 1 / 3',
        description: 'Các token được chấp nhận được commit vào Output Buffer trước khi bắt đầu cycle tiếp theo.',
        node: 'nBuffer',
        activeEdge: 'output-buffer-to-draft-loop',
        packet: 'accepted',
        context: '11 accepted tokens',
        process: 'Append to Output Buffer',
        output: '11 committed tokens',
        log: 'Cycle 1 hoàn tất; bắt đầu Cycle 2.',
        cycleBadge: 'CYCLE 1 / 3'
    },
    {
        title: 'DRAFT BLOCK ỨNG VIÊN',
        stage: 'DRAFT · CYCLE 2 / 3',
        description: 'Draft model đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.',
        node: 'nDraft',
        activeEdge: 'draft-to-verify',
        packet: 'draft block',
        context: 'Current accepted context',
        process: 'Draft 16 candidate tokens · Cycle 2 / 3',
        output: '16 candidate tokens',
        log: 'Draft model đã đề xuất block token thứ 2.',
        cycleBadge: 'CYCLE 2 / 3'
    },
    {
        title: 'TARGET KIỂM CHỨNG',
        stage: 'VERIFY · CYCLE 2 / 3',
        description: 'Mô hình đích kiểm chứng block ứng viên, chấp nhận prefix phù hợp và loại phần không khớp.',
        node: 'nVerify',
        activeEdge: 'verify-to-output-buffer',
        packet: 'verify',
        context: '16 candidate tokens',
        process: 'Target verification · Cycle 2 / 3',
        output: '13 accepted · 3 rejected',
        log: '13 token được commit; Output Buffer đạt 24 token.',
        cycleBadge: 'CYCLE 2 / 3'
    },
    {
        title: 'TIẾP TỤC VÒNG SINH',
        stage: 'LOOP · CYCLE 2 / 3',
        description: 'Các token được chấp nhận được commit vào Output Buffer trước khi bắt đầu cycle tiếp theo.',
        node: 'nBuffer',
        activeEdge: 'output-buffer-to-draft-loop',
        packet: 'accepted',
        context: '13 accepted tokens',
        process: 'Append to Output Buffer',
        output: '24 committed tokens',
        log: 'Cycle 2 hoàn tất; bắt đầu Cycle 3.',
        cycleBadge: 'CYCLE 2 / 3'
    },
    {
        title: 'DRAFT BLOCK ỨNG VIÊN',
        stage: 'DRAFT · CYCLE 3 / 3',
        description: 'Draft model đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.',
        node: 'nDraft',
        activeEdge: 'draft-to-verify',
        packet: 'draft block',
        context: 'Current accepted context',
        process: 'Draft 16 candidate tokens · Cycle 3 / 3',
        output: '16 candidate tokens',
        log: 'Draft model đã đề xuất block token thứ 3.',
        cycleBadge: 'CYCLE 3 / 3'
    },
    {
        title: 'TARGET KIỂM CHỨNG',
        stage: 'VERIFY · CYCLE 3 / 3',
        description: 'Mô hình đích kiểm chứng block ứng viên, chấp nhận prefix phù hợp và loại phần không khớp.',
        node: 'nVerify',
        activeEdge: 'verify-to-output-buffer',
        packet: 'verify',
        context: '16 candidate tokens',
        process: 'Target verification · Cycle 3 / 3',
        output: '9 accepted · 7 rejected',
        log: '9 token được commit; Output Buffer đạt 33 token.',
        cycleBadge: 'CYCLE 3 / 3'
    },
    {
        title: 'HOÀN TẤT GENERATION',
        stage: 'OUTPUT · CYCLE 3 / 3',
        description: 'Output Buffer được hoàn tất và chuyển thành câu trả lời cuối cùng.',
        node: 'nFinal',
        activeEdge: 'dflash-container-to-final-output',
        packet: 'completion',
        context: '33 committed tokens',
        process: 'Finalize generated response',
        output: 'Final output ready',
        log: 'D-Flash hoàn tất sau 3 cycle draft–verify.',
        cycleBadge: 'CYCLE 3 / 3'
    }
];\n\n` + mockData.substring(arrayEnd);

fs.writeFileSync('mocks/mock-data.js', newMockData);

// 2. Modifying architecture-graph.js
let graphJs = fs.readFileSync('scripts/architecture-graph.js', 'utf-8');

// We need to add the new query selectors for process and event
graphJs = graphJs.replace("const contextBox = document.querySelector('.insp-box--input') || document.getElementById('contextBox');",
    "const contextBox = document.querySelector('.insp-box--input') || document.getElementById('contextBox');\n    const processBox = document.querySelector('.insp-box--process');\n    const eventBox = document.querySelector('.insp-box--event');");

// And the cycle badge inside the D-Flash container!
graphJs = graphJs.replace("const cycleLabel = document.querySelector('.insp-badge--state') || document.getElementById('cycleLabel');",
    "const cycleLabel = document.querySelector('.insp-badge--state') || document.getElementById('cycleLabel');\n    const containerBadge = document.getElementById('containerCycleBadge');");


// Remove old activeEdgesByStep
graphJs = graphJs.replace(/const activeEdgesByStep = \{[\s\S]*?\};/, '');

// Fix active edges assignment
graphJs = graphJs.replace("const activeEdges = activeEdgesByStep[index] || [];",
    "const activeEdges = step.activeEdge ? [step.activeEdge] : [];");

// Fix DOM assignment logic in renderStep
let renderUpdates = `
        if (stepTitle) stepTitle.textContent = step.title;
        if (stepDesc) stepDesc.textContent = step.description;
        if (cycleChip) cycleChip.textContent = step.stage;
        if (cycleLabel) cycleLabel.textContent = \`Stage: \${step.stage.toLowerCase()}\`;
        if (contextBox) contextBox.textContent = step.context || '—';
        if (processBox) processBox.textContent = step.process || '—';
        if (payloadBox) payloadBox.textContent = step.output || '—';
        if (eventBox) eventBox.textContent = step.log || '—';
        if (containerBadge) containerBadge.textContent = step.cycleBadge ? 'CYCLE: ' + step.cycleBadge.replace('CYCLE ', '') : 'CYCLE: IDLE';
        if (bar) bar.style.width = \`\${((index + 1) / architectureSteps.length) * 100}%\`;
`;
graphJs = graphJs.replace(/if \(stepTitle\) stepTitle\.textContent = step\.title;[\s\S]*?if \(bar\) bar\.style\.width = `\${\(\(index \+ 1\) \/ architectureSteps\.length\) \* 100}%`;/, renderUpdates.trim());

// Fix DOM assignment logic for index < 0 (initial state)
let initUpdates = `
        if (stepTitle) stepTitle.textContent = 'CHƯA BẮT ĐẦU';
        if (stepDesc) stepDesc.textContent = 'Nhấn Next để theo dõi dữ liệu đi qua từng thành phần của pipeline CC-DFlash.';
        if (cycleChip) cycleChip.textContent = 'WALKTHROUGH';
        if (cycleLabel) cycleLabel.textContent = 'READY';
        if (contextBox) contextBox.textContent = '—';
        if (processBox) processBox.textContent = 'Chưa có bước xử lý';
        if (payloadBox) payloadBox.textContent = '—';
        if (eventBox) eventBox.textContent = 'Walkthrough chưa bắt đầu.';
        if (containerBadge) containerBadge.textContent = 'CYCLE: IDLE';
        if (logBox) logBox.innerHTML = '<div>CC-DFlash simulation initialized.</div>';
        if (bar) bar.style.width = '0%';
`;
graphJs = graphJs.replace(/if \(stepTitle\) stepTitle\.textContent = 'CHƯA BẮT ĐẦU';[\s\S]*?if \(bar\) bar\.style\.width = '0%';/, initUpdates.trim());

fs.writeFileSync('scripts/architecture-graph.js', graphJs);

console.log('Scripts updated successfully.');
