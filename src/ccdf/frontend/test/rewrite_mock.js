const fs = require('fs');
let js = fs.readFileSync('mocks/mock-data.js', 'utf8');

const regex = /export const architectureSteps = \[[\s\S]*?(?=\s*\{\s*id: "target-prefill")/m;
const replacement = `export const architectureSteps = [
  {
    id: "original-prompt",
    node: "nInput",
    activeEdge: null,
    title: "ORIGINAL PROMPT",
    description: "Nhận nguyên văn prompt do người dùng nhập trước khi phân tách và xử lý.",
    accent: "yellow",
    trace: {
      "TRẠNG THÁI": "PROMPT RECEIVED",
      "TOKENS ƯỚC TÍNH": originalTokens.toString()
    }
  },
  {
    id: "prompt-segmenter",
    node: "nSplit",
    activeEdge: ["segmenter-to-llmlingua", "segmenter-to-protected-question"],
    title: "PROMPT SEGMENTER",
    description: "Tách prompt thành hai nhánh được xử lý đồng thời: ngữ cảnh cần nén và câu hỏi cần giữ nguyên.",
    accent: "cyan",
    trace: {
      "TRẠNG THÁI": "SPLIT INTO 2 BRANCHES",
      "BRANCH": "2",
      "CONTEXT TOKENS": contextTokens.toString(),
      "PROTECTED TOKENS": protectedTokens.toString()
    }
  },
  {
    id: "llmlingua-2",
    node: "nCompress",
    activeEdge: "segmenter-to-llmlingua",
    title: "COMPRESSOR",
    description: "LLMLingua-2 loại bỏ phần diễn đạt dư thừa và giữ lại thông tin cần thiết trong ngữ cảnh.",
    accent: "pink",
    trace: {
      "TRẠNG THÁI": "CONTEXT COMPRESSED",
      "INPUT TOKENS": contextTokens.toString(),
      "OUTPUT TOKENS": compressedTokens.toString(),
      "REDUCTION": reduction
    }
  },
  {
    id: "protected-question",
    node: "nProtect",
    activeEdge: "segmenter-to-protected-question",
    title: "PROTECTED QUESTION",
    description: "Giữ nguyên câu hỏi và yêu cầu trả lời, không đưa phần này qua bộ nén.",
    accent: "lime",
    trace: {
      "TRẠNG THÁI": "QUESTION LOCKED",
      "TOKENS": protectedTokens.toString(),
      "CHANGE": "NONE"
    }
  },
  {
    id: "prompt-compression",
    node: "nMerge",
    activeEdge: "context-compression-to-prompt-compression",
    title: "PROMPT COMPRESSION",
    description: "Ghép ngữ cảnh sau xử lý với câu hỏi được bảo vệ để tạo prompt cuối.",
    accent: "purple",
    trace: {
      "TRẠNG THÁI": "PROMPT MERGED",
      "OUTPUT TOKENS": finalTokens.toString(),
      "SOURCES": "2"
    }
  },`;

const newJs = js.replace(regex, replacement);
if (newJs === js) {
    console.error("No change!");
    process.exit(1);
}
fs.writeFileSync('mocks/mock-data.js', newJs);
console.log("Success Mock");
