(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),e.crossOrigin===`use-credentials`?t.credentials=`include`:e.crossOrigin===`anonymous`?t.credentials=`omit`:t.credentials=`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})();var e={context:`ê tui đang tìm cái bài nổi nổi trên toktok, hình như có câu “gòi mưa giông đến đây thiếu vắng một bóng hình hông phai”, nó là remix giực giưc nghe quen lắm mà không nhớ  bài gì`,protectedQuestion:`lyric tiếp theo là gì nhỉ?`,compressedContext:`bài nổi trên toktok, câu “gòi mưa giông đến đây thiếu vắng một bóng hình hông phai”, remix giực giưc`};e.originalPrompt=`${e.context}\n\n${e.protectedQuestion}`,e.finalCompressedPrompt=`${e.compressedContext}\n\n${e.protectedQuestion}`;var t=e=>Math.ceil(e.length/4),n=t(e.originalPrompt),r=t(e.context),i=t(e.protectedQuestion),a=t(e.compressedContext),o=t(e.finalCompressedPrompt),s=Math.round((r-a)/r*100)+`%`,c=[{id:`original-prompt`,node:`nInput`,activeEdge:null,title:`ORIGINAL PROMPT`,description:`Nhận nguyên văn prompt do người dùng nhập trước khi phân tách và xử lý.`,accent:`yellow`,trace:{"TRẠNG THÁI":`PROMPT RECEIVED`,"TOKENS ƯỚC TÍNH":n.toString()}},{id:`prompt-segmenter`,node:`nSplit`,activeEdge:[`segmenter-to-llmlingua`,`segmenter-to-protected-question`],title:`PROMPT SEGMENTER`,description:`Tách prompt thành hai nhánh được xử lý đồng thời: ngữ cảnh cần nén và câu hỏi cần giữ nguyên.`,accent:`cyan`,trace:{"TRẠNG THÁI":`SPLIT INTO 2 BRANCHES`,BRANCH:`2`,"CONTEXT TOKENS":r.toString(),"PROTECTED TOKENS":i.toString()}},{id:`llmlingua-2`,node:`nCompress`,activeEdge:`segmenter-to-llmlingua`,title:`COMPRESSOR`,description:`LLMLingua-2 loại bỏ phần diễn đạt dư thừa và giữ lại thông tin cần thiết trong ngữ cảnh.`,accent:`pink`,trace:{"TRẠNG THÁI":`CONTEXT COMPRESSED`,"INPUT TOKENS":r.toString(),"OUTPUT TOKENS":a.toString(),REDUCTION:s}},{id:`protected-question`,node:`nProtect`,activeEdge:`segmenter-to-protected-question`,title:`PROTECTED QUESTION`,description:`Giữ nguyên câu hỏi và yêu cầu trả lời, không đưa phần này qua bộ nén.`,accent:`lime`,trace:{"TRẠNG THÁI":`QUESTION LOCKED`,TOKENS:i.toString(),CHANGE:`NONE`}},{id:`prompt-compression`,node:`nMerge`,activeEdge:[`context-compression-to-prompt-compression`,`prompt-compression-to-dflash`],title:`PROMPT COMPRESSION`,description:`Ghép ngữ cảnh sau xử lý với câu hỏi được bảo vệ để tạo prompt cuối.`,accent:`purple`,trace:{"TRẠNG THÁI":`PROMPT MERGED`,"OUTPUT TOKENS":o.toString(),SOURCES:`2`}},{id:`target-prefill`,node:`nPrefill`,activeEdge:`prefill-to-draft`,title:`TARGET PREFILL`,description:`Mô hình đích xử lý prompt đã rút gọn và tạo context state cho D-Flash.`,accent:`orange`,trace:{metric:`124 INPUT TOKENS`,input:`124 prompt tokens · context nén + ràng buộc nguyên vẹn`,operation:`TARGET PREFILL`,output:`Target cache ready · sẵn sàng cho D-Flash generation`}},{id:`draft-cycle-1`,node:`nDraft`,activeEdge:`draft-to-verify`,title:`DRAFT — CYCLE 1`,description:`Đề xuất một block gồm 16 candidate token từ trạng thái generation hiện tại.`,accent:`cyan`,trace:{metric:`8 CANDIDATE TOKENS`,input:`Target cache + output prefix rỗng`,operation:`DRAFT · CYCLE 1 / 3`,output:`Ứng viên: “[lyric] [tiếp] [theo] [là] [đây]...”`}},{id:`verify-cycle-1`,node:`nVerify`,activeEdge:`verify-to-output-buffer`,title:`VERIFY — CYCLE 1`,description:`Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.`,accent:`purple`,trace:{metric:`4 / 8 ACCEPTED`,input:`8 candidate tokens từ Cycle 1`,operation:`TARGET VERIFY · CYCLE 1 / 3`,output:`4 accepted · 1 rejected (đây -> Bàn) · Buffer: 5 tokens`}},{id:`loop-cycle-1`,node:`nBuffer`,activeEdge:`output-buffer-to-prefill`,title:`LOOP — CYCLE 1`,description:`Tích lũy các token đã được target chấp nhận qua từng cycle.`,accent:`blue`,trace:{metric:`BUFFER 5`,input:`4 accepted tokens + 1 corrected`,operation:`COMMIT VÀ LOOP`,output:`Đã lưu: lyric tiếp theo là Bàn · bắt đầu Cycle 2 / 3`}},{id:`draft-cycle-2`,node:`nDraft`,activeEdge:`draft-to-verify`,title:`DRAFT — CYCLE 2`,description:`Đề xuất một block gồm 8 candidate token từ trạng thái generation hiện tại.`,accent:`cyan`,trace:{metric:`8 CANDIDATE TOKENS`,input:`Output prefix: 5 committed tokens`,operation:`DRAFT · CYCLE 2 / 3`,output:`Ứng viên: “[chân] [ai] [chờ] [ai]...”`}},{id:`verify-cycle-2`,node:`nVerify`,activeEdge:`verify-to-output-buffer`,title:`VERIFY — CYCLE 2`,description:`Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.`,accent:`purple`,trace:{metric:`2 / 8 ACCEPTED`,input:`8 candidate tokens từ Cycle 2`,operation:`TARGET VERIFY · CYCLE 2 / 3`,output:`2 accepted · 1 rejected (chờ -> đợi) · Buffer: 8 tokens`}},{id:`loop-cycle-2`,node:`nBuffer`,activeEdge:`output-buffer-to-prefill`,title:`LOOP — CYCLE 2`,description:`Tích lũy các token đã được target chấp nhận qua từng cycle.`,accent:`blue`,trace:{metric:`BUFFER 8`,input:`2 accepted tokens + 1 corrected`,operation:`COMMIT VÀ LOOP`,output:`Đã lưu: Bàn chân ai đợi · bắt đầu Cycle 3 / 3`}},{id:`draft-cycle-3`,node:`nDraft`,activeEdge:`draft-to-verify`,title:`DRAFT — CYCLE 3`,description:`Đề xuất một block gồm 8 candidate token từ trạng thái generation hiện tại.`,accent:`cyan`,trace:{metric:`8 CANDIDATE TOKENS`,input:`Output prefix: 8 committed tokens`,operation:`DRAFT · CYCLE 3 / 3`,output:`Ứng viên: “[ai] [nghe] [tiếng] [khóc]...”`}},{id:`verify-cycle-3`,node:`nVerify`,activeEdge:`verify-to-output-buffer`,title:`VERIFY — CYCLE 3`,description:`Mô hình đích kiểm chứng block ứng viên và chấp nhận prefix phù hợp.`,accent:`purple`,trace:{metric:`7 / 8 ACCEPTED`,input:`8 candidate tokens từ Cycle 3`,operation:`TARGET VERIFY · CYCLE 3 / 3`,output:`7 accepted · 1 empty · Buffer: 15 tokens`}},{id:`buffer-complete`,node:`nBuffer`,activeEdge:`dflash-to-final-output`,title:`OUTPUT BUFFER COMPLETE`,description:`Hoàn tất output buffer sau khi thực thi đủ các cycle D-Flash.`,accent:`blue`,trace:{metric:`BUFFER 15`,input:`15 committed tokens sau ba cycle`,operation:`HOÀN TẤT OUTPUT BUFFER`,output:`Đã tạo xong câu trả lời cho người dùng`}},{id:`final-output`,node:`nFinal`,activeEdge:null,title:`FINAL OUTPUT`,description:`Hoàn tất câu trả lời sau ba cycle draft–verify.`,accent:`blue`,trace:{metric:`FINAL RESPONSE`,input:`Completed Output Buffer`,operation:`FINALIZE`,output:`lyric tiếp theo là Bàn chân ai đợi ai nghe tiếng khóc trong đêm dài`}}],l={gsm8k:{label:`GSM8K · short numeric prompt`,prompt:`Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?

Return the result on the final line using: Final answer: <number>`},qmsum:{label:`QMSum · long meeting context`,prompt:`Meeting transcript:

Alice: We need to decide how the mobile release should handle offline synchronization. The current build retries every ten seconds, but this causes duplicate uploads when the connection is unstable.

Bob: The backend team can add idempotency keys, although that will not land before the next release candidate. For the short term, the client could queue changes locally and retry only after the network state has been stable for thirty seconds.

Carla: Product wants the release this Friday. We can accept a limited offline mode if the interface clearly shows which records are pending. We should not silently discard edits.

Alice: Then the proposal is to keep local changes, display a pending badge, wait for a stable connection, and retry. Duplicate protection will be added on the server in the following sprint.

Bob: I agree, but analytics events should not be queued with business records. They can be dropped if the app is closed.

Carla: Please document that distinction in the release notes and create a follow-up ticket for server-side idempotency.

Question: What decision did the team make about offline synchronization for the upcoming release, and what work was deferred?`},custom:{label:`Custom prompt`,prompt:`Tối thứ Bảy tôi mời 8 người ăn tối. Có 2 người ăn chay, 1 người dị ứng đậu phộng và 1 người không ăn cay. Nhà có 2 vùng nấu, 1 nồi và 1 chảo; mọi người thích món Việt, dễ chia phần và chuẩn bị nhanh.

Hãy đề xuất thực đơn 3 món, tổng chi phí không quá 1.500.000đ. Bắt đầu lúc 18:30, xong trước 21:00. Trả lời đúng 4 gạch đầu dòng và không dùng đậu phộng.`}},u=[[`Original input tokens`,`Estimated tokens in the full prompt before any compression.`],[`Effective prefill tokens`,`Tokens actually processed during target prefill. Baseline-AR and D-Flash use the full input; CC-DFlash uses the compressed prompt.`],[`Compression ratio`,`Original input tokens divided by compressed input tokens. Only applies to CC-DFlash.`],[`Compression overhead`,`CPU time spent compressing the context before model inference.`],[`Prefill latency`,`Time required for the target model to process the input prompt and initialize the cache.`],[`Generation latency`,`Time spent generating output tokens after prefill.`],[`End-to-end latency`,`Compression overhead + prefill + generation. This is the conservative comparison metric.`],[`Generation throughput`,`Output tokens divided by generation latency. It does not include compression or prefill.`],[`Acceptance length τ`,`Average number of draft tokens accepted per DFlash verification step. Not applicable to Baseline-AR.`],[`Numeric quality proxy`,`GSM8K uses final numeric answer matching as a deterministic quality signal.`],[`Lexical overlap proxy`,`QMSum uses normalized overlap as diagnostic evidence, not semantic correctness.`],[`Workload class`,`Short, medium, or long context. Compression becomes more useful as prefill savings can offset its overhead.`]],d=(e,t)=>new Promise(n=>{let r=window.setTimeout(n,e);t?.addEventListener(`abort`,()=>{window.clearTimeout(r),n()},{once:!0})});function f(){let t=document.getElementById(`graphViewport`),n=document.getElementById(`graphScene`),r=document.getElementById(`stepTitle`),i=document.getElementById(`stepDesc`),a=document.getElementById(`stepIndicator`),o=document.getElementById(`live-data-fields`);document.getElementById(`logBox`);let s=document.getElementById(`zoomLevel`),l=document.getElementById(`runBtn`),u=document.getElementById(`autoBtn`),f=document.getElementById(`zoomOutBtn`),p=document.getElementById(`zoomInBtn`),m=document.getElementById(`zoomFitBtn`),h=window.matchMedia(`(prefers-reduced-motion: reduce)`).matches,g=-1,_=!1,v=new AbortController,y=1,b=0,x=0,S=null,C=[...n.querySelectorAll(`.node`)],w=[...n.querySelectorAll(`.edge`)],T=document.getElementById(`nInput-content`);T&&(T.textContent=e.originalPrompt);let E=document.getElementById(`nSplit-context`);E&&(E.textContent=e.context);let D=document.getElementById(`nSplit-protected`);D&&(D.textContent=e.protectedQuestion);let O=document.getElementById(`nCompress-input`);O&&(O.textContent=e.context);let k=document.getElementById(`nCompress-output`);k&&(k.textContent=e.compressedContext);let A=document.getElementById(`nProtect-content`);A&&(A.textContent=e.protectedQuestion);let j=document.getElementById(`nMerge-content`);j&&(j.textContent=e.finalCompressedPrompt),n.querySelector(`svg.edges`);function M(){n.style.transform=`translate(${b}px, ${x}px) scale(${y})`,s&&(s.textContent=`${Math.round(y*100)}%`)}function N(){let e=t.getBoundingClientRect(),n=2200,r=1700,i=e.width>900?345:0,a=e.width-i,o=Math.min(a/n,e.height/r);y=Math.min(1.8,Math.max(.3,o)),b=i+(a-n*y)/2,x=(e.height-r*y)/2,M()}function P(){C.forEach(e=>e.classList.remove(`active`,`completed`)),w.forEach(e=>e.classList.remove(`is-active`))}function F(e,{log:t=!0}={}){if(e<0||e>=c.length)return;g=e;let n=c[e];if(P(),c.slice(0,e).forEach(e=>{document.getElementById(e.node)?.classList.add(`completed`)}),document.getElementById(n.node)?.classList.add(`active`),(n.activeEdge?Array.isArray(n.activeEdge)?n.activeEdge:[n.activeEdge]:[]).forEach(e=>{document.getElementById(e)?.classList.add(`is-active`)}),r&&(r.textContent=n.title),i&&(i.textContent=n.description),a){let t=e.toString().padStart(2,`0`);a.textContent=`STEP ${t} / ${c.length-1}`}if(o&&(o.innerHTML=``,n.trace)){let e=n.trace;!e[`TRẠNG THÁI`]&&e.operation&&(e={"TRẠNG THÁI":e.operation,METRIC:e.metric,INPUT:e.input,OUTPUT:e.output}),Object.entries(e).forEach(([e,t])=>{if(t){let r=document.createElement(`div`);r.style.display=`flex`,r.style.flexDirection=`column`,r.style.gap=`2px`;let i=document.createElement(`span`);i.textContent=e,i.style.fontSize=`11px`,i.style.fontWeight=`900`,i.style.textTransform=`uppercase`;let a=document.createElement(`div`);a.textContent=t,a.style.background=`#fff`,a.style.border=`2px solid #111`,a.style.borderLeft=`6px solid var(--cyan)`,a.style.padding=`6px 10px`,a.style.fontSize=`13px`,a.style.fontWeight=`700`;let s=n.accent?`var(--${n.accent})`:`var(--cyan)`;a.style.borderLeftColor=s,r.appendChild(i),r.appendChild(a),o.appendChild(r)}})}let s=document.getElementById(`nPrefill-prefix`),l=document.getElementById(`nPrefill-state`),u=document.getElementById(`nDraft-slots`),d=document.getElementById(`nVerify-slots`),f=document.getElementById(`nBuffer-content`);function p(e,t){e.innerHTML=t.map(e=>{if(!e||!e.t)return`<div class="draft-slot empty">&nbsp;</div>`;let t=`<div class="${[`draft-slot`,e.s].join(` `).trim()}">${e.t}</div>`;return e.s===`rejected`&&e.c&&(t+=`<div class="draft-slot corrected">${e.c}</div>`),t}).join(``)}let m={cycle1:{prefix:`[Trống - Bắt đầu sinh]`,state:`Target cache ready`,draft:[{t:`lyric`,s:``},{t:`tiếp`,s:``},{t:`theo`,s:``},{t:`là`,s:``},{t:`đây`,s:``},{t:`là`,s:``},{t:`bài`,s:``},{t:`này`,s:``}],verify:[{t:`lyric`,s:`accepted`},{t:`tiếp`,s:`accepted`},{t:`theo`,s:`accepted`},{t:`là`,s:`accepted`},{t:`đây`,s:`rejected`,c:`Bàn`},{t:`là`,s:`discarded`},{t:`bài`,s:`discarded`},{t:`này`,s:`discarded`}],buffer:`lyric tiếp theo là Bàn`},cycle2:{prefix:`lyric tiếp theo là Bàn`,state:`Updated cache with Cycle 1`,draft:[{t:`chân`,s:``},{t:`ai`,s:``},{t:`chờ`,s:``},{t:`ai`,s:``},{t:`nghe`,s:``},{t:`tiếng`,s:``},{t:`khóc`,s:``},{t:`trong`,s:``}],verify:[{t:`chân`,s:`accepted`},{t:`ai`,s:`accepted`},{t:`chờ`,s:`rejected`,c:`đợi`},{t:`ai`,s:`discarded`},{t:`nghe`,s:`discarded`},{t:`tiếng`,s:`discarded`},{t:`khóc`,s:`discarded`},{t:`trong`,s:`discarded`}],buffer:`lyric tiếp theo là Bàn chân ai đợi`},cycle3:{prefix:`lyric tiếp theo là Bàn chân ai đợi`,state:`Updated cache with Cycle 2`,draft:[{t:`ai`,s:``},{t:`nghe`,s:``},{t:`tiếng`,s:``},{t:`khóc`,s:``},{t:`trong`,s:``},{t:`đêm`,s:``},{t:`dài`,s:``},{t:``,s:``}],verify:[{t:`ai`,s:`accepted`},{t:`nghe`,s:`accepted`},{t:`tiếng`,s:`accepted`},{t:`khóc`,s:`accepted`},{t:`trong`,s:`accepted`},{t:`đêm`,s:`accepted`},{t:`dài`,s:`accepted`},{t:``,s:`empty`}],buffer:`lyric tiếp theo là Bàn chân ai đợi ai nghe tiếng khóc trong đêm dài`}};function h(e){let t=[...e];for(;t.length<40;)t.push({t:``,s:`empty`});return t}if(s&&u&&d&&f){let t=document.getElementById(`nDraft-loop-label`),r=document.getElementById(`nVerify-loop-label`),i=document.getElementById(`nFinal-content`);if(e<6){t&&(t.textContent=`DRAFT BLOCK — WAITING`),r&&(r.textContent=`VERIFY — WAITING`),s.textContent=`[Chờ dữ liệu...]`,l&&(l.textContent=`[Chờ khởi tạo]`);let e=h([]);p(u,e),p(d,e),f.textContent=`[Trống]`,i&&(i.textContent=`[Đang chờ...]`)}else{let e=m.cycle1;n.id.includes(`cycle-2`)&&(e=m.cycle2),(n.id.includes(`cycle-3`)||n.id===`buffer-complete`||n.id===`final-output`)&&(e=m.cycle3);let a=n.id.includes(`cycle-2`)?2:n.id.includes(`cycle-3`)||n.id===`buffer-complete`||n.id===`final-output`?3:1;t&&(t.textContent=`DRAFT BLOCK — LOOP ${a}`),r&&(r.textContent=`VERIFY — LOOP ${a}`),s.textContent=e.prefix,l&&(l.textContent=e.state),p(u,h(e.draft)),n.id.includes(`prefill`)||n.id===`draft-cycle-${a}`?p(d,h(e.draft.map(e=>({t:e.t,s:`empty`})))):p(d,h(e.verify)),n.id===`loop-cycle-${a}`||n.id===`buffer-complete`||n.id===`final-output`?f.textContent=e.buffer:a>1?f.textContent=m[`cycle${a-1}`].buffer:f.textContent=`[Trống]`,i&&(n.id===`final-output`?i.textContent=e.buffer:i.textContent=`[Đang sinh...]`)}}let _=n.accent?`var(--${n.accent})`:`var(--cyan)`;a&&(a.style.background=_),prevBtn&&(prevBtn.disabled=e===0),nextBtn&&(nextBtn.disabled=e===c.length-1)}function I(){v.abort(),v=new AbortController,_=!1,u&&(u.classList.remove(`is-playing`),u.textContent=`Auto Play`),l&&(l.disabled=!1)}function L(){I(),g=0,P(),F(0,{log:!1}),N()}async function R(){I();let e=v;l.disabled=!0;for(let t=0;t<c.length&&!e.signal.aborted;t+=1)F(t),await d(h?120:820,e.signal);e.signal.aborted||(l.disabled=!1)}async function z(){if(_){I();return}I(),_=!0,u.classList.add(`is-playing`),u.textContent=`Pause`;let e=v,t=g<0||g>=c.length-1?0:g+1;for(;_&&!e.signal.aborted;)F(t),await d(h?220:1050,e.signal),t=(t+1)%c.length}l&&l.addEventListener(`click`,R),u&&u.addEventListener(`click`,z),resetBtn&&resetBtn.addEventListener(`click`,L),nextBtn&&nextBtn.addEventListener(`click`,()=>{I(),F(Math.min(g+1,c.length-1))}),prevBtn&&prevBtn.addEventListener(`click`,()=>{I(),F(Math.max(g-1,0))}),p&&p.addEventListener(`click`,()=>{y=Math.min(1.8,y+.1),M()}),f&&f.addEventListener(`click`,()=>{y=Math.max(.55,y-.1),M()}),m&&m.addEventListener(`click`,N),t.addEventListener(`pointerdown`,e=>{e.target.closest(`button`)||(e.preventDefault(),t.focus(),S={x:e.clientX,y:e.clientY,translateX:b,translateY:x},t.setPointerCapture(e.pointerId),t.classList.add(`is-dragging`))}),t.addEventListener(`pointermove`,e=>{S&&(b=S.translateX+e.clientX-S.x,x=S.translateY+e.clientY-S.y,requestAnimationFrame(M))});let B=e=>{S&&(S=null,t.classList.remove(`is-dragging`),t.hasPointerCapture(e.pointerId)&&t.releasePointerCapture(e.pointerId))};t.addEventListener(`pointerup`,B),t.addEventListener(`pointercancel`,B),t.addEventListener(`wheel`,e=>{if(!e.ctrlKey||document.activeElement!==t&&!t.contains(document.activeElement))return;e.preventDefault();let n=t.getBoundingClientRect(),r=e.clientX-n.left,i=e.clientY-n.top,a=(r-b)/y,o=(i-x)/y,s=e.deltaY>0?-.1:.1,c=Math.min(1.8,Math.max(.55,y+s));b=r-a*c,x=i-o*c,y=c,M()},{passive:!1}),t.addEventListener(`keydown`,e=>{if(e.key===`Escape`){t.blur();return}e.key===`ArrowRight`&&(e.preventDefault(),I(),F(Math.min(g+1,c.length-1))),e.key===`ArrowLeft`&&(e.preventDefault(),I(),F(Math.max(g-1,0)))}),window.addEventListener(`resize`,N),L(),N()}var p=(e,t=0)=>Number(e.toFixed(t));function m(e){return e==null?`—`:e>=1e3?`${p(e/1e3,2)} s`:`${Math.round(e)} ms`}function h(e){let t=e.trim(),n=t?t.split(/\s+/).length:0,r=t.length;return{words:n,characters:r,estimatedTokens:Math.max(8,Math.ceil(r/4.2+n*.18))}}function g(e){let t=e.toLowerCase();return t.includes(`warm end-to-end`)||t.includes(`e2e vs`)?`m-speed`:t.includes(`throughput`)?`m-tps`:t.includes(`prefill`)?`m-lat`:t.includes(`generation latency`)?`m-cyan`:t.includes(`compression`)?`m-compress`:t.includes(`tau`)||t.includes(`acceptance`)?`m-accept`:`m-token`}function _(e,t){let n=e.condition_id===`baseline-ar`?`(reference)`:t&&e.warm_request_e2e_ms!=null?`${p((t-e.warm_request_e2e_ms)/t*100,1)}% ${t>e.warm_request_e2e_ms?`faster`:`slower`} than Baseline`:`—`,r=!e.compression_applied&&!e.compression_bypassed?`not applied`:e.compression_bypassed?`bypassed (${e.compression_bypass_reason||`unknown`})`:e.compression_ratio==null?`—`:`${p(e.compression_ratio,2)}×`;return[[`Input tokens`,e.input_tokens_precompression==null?`—`:e.input_tokens_precompression.toLocaleString(`en-US`)],[`Effective prefill`,e.input_tokens_final==null?`—`:e.input_tokens_final.toLocaleString(`en-US`)],[`Compression ratio`,r],[`Compression overhead`,e.compression_total_ms==null?`0 ms`:m(e.compression_total_ms)],[`Prefill latency`,m(e.target_prefill_ms)],[`Generation latency`,m(e.decode_total_ms)],[`Warm end-to-end`,m(e.warm_request_e2e_ms)],[`Generation throughput`,e.generation_tok_s==null?`—`:`${p(e.generation_tok_s,1)} tok/s`],[`Acceptance τ`,e.effective_tau==null?`—`:p(e.effective_tau,2)],[`Warm E2E vs Baseline`,n]]}function v(e,t,n){let r=_(t,n);document.getElementById(e).innerHTML=r.map(([e,t])=>`<div class="metric ${g(e)}"><span>${e}</span><b>${t}</b></div>`).join(``)}function y(e,t){let n=document.getElementById(e);n&&(n.textContent=t,n.className=`status ${t===`RUNNING`?`running`:t===`DONE`?`done`:t===`FAILED`?`failed`:``}`)}function b(e){let t=document.getElementById(`compareSteps`);t&&[...t.children].forEach((t,n)=>{t.className=`step ${n<e?`done`:n===e?`active`:``}`})}function x(e,t){for(let[,e]of Object.entries({"baseline-ar":{resp:`baselineResponse`,status:`baselineStatus`,progress:`baselineProgress`},"dflash-r1":{resp:`dflashResponse`,status:`dflashStatus`,progress:`dflashProgress`},"cc-dflash-r2":{resp:`ccResponse`,status:`ccStatus`,progress:`ccProgress`},"cc-dflash-r2-gpu":{resp:`ccResponse`,status:`ccStatus`,progress:`ccProgress`}})){let n=document.getElementById(e.status);if(n&&n.textContent===`RUNNING`){y(e.status,`FAILED`);let n=document.getElementById(e.resp);n&&(n.textContent=`Error: ${t}`);let r=document.getElementById(e.progress);r&&(r.style.display=`none`)}}}function S(e){let t=e[`baseline-ar`],n=e[`dflash-r1`],r=e[`cc-dflash-r2-gpu`]||e[`cc-dflash-r2`];if(!t||!n||!r)return`<p>Incomplete results — one or more conditions did not complete.</p>`;let i=[t,n,r].reduce((e,t)=>(e.warm_request_e2e_ms??1/0)<(t.warm_request_e2e_ms??1/0)?e:t),a=r.compression_bypassed&&r.compression_bypass_reason===`empty_context`,o=r.compression_bypassed,s=a?`question-only (compressor not loaded)`:o?`compression bypass (${r.compression_bypass_reason||`short context`})`:`compressed context`,c=t.decode_total_ms&&n.decode_total_ms?t.decode_total_ms/n.decode_total_ms:null,l=r.prompt_reduction_pct==null?`n/a`:`${p(r.prompt_reduction_pct,1)}%`,u=r.warm_request_e2e_ms,d=n.warm_request_e2e_ms,f;return f=a?`Workload is question-only. CC-DFlash gracefully bypasses compression; compressor was not loaded.`:o?`Context was too short to compress. Passthrough was used.`:u!=null&&d!=null&&u<d?`Compression savings offset overhead. CC-DFlash is faster end-to-end than D-Flash.`:`Compression overhead exceeds savings. D-Flash is faster end-to-end than CC-DFlash for this workload.`,`
        <div class="summary-grid">
            <div><span>Workload</span><b>${s}</b></div>
            <div><span>Fastest warm E2E</span><b>${i.display_name}</b></div>
            <div><span>CC prompt reduction</span><b>${l}</b></div>
            <div><span>DFlash gen speedup</span><b>${c==null?`n/a`:p(c,2)+`×`}</b></div>
        </div>
        <p>${f}</p>
        <p class="summary-caveat">Results generated from real model execution using a generic demo policy. Not a canonical benchmark run.</p>
    `}async function C(){let e=document.getElementById(`demoPreset`),t=document.getElementById(`comparePrompt`),n=document.getElementById(`inputStats`),r=document.getElementById(`compressionDevice`),i=document.getElementById(`compareStart`),a=document.getElementById(`compareReset`),o=document.getElementById(`comparisonSummary`),s=document.getElementById(`comparisonSummaryBody`),c=null,u=null,d={},f=!0;try{let e=await fetch(`/api/capabilities`).then(e=>e.json());if(!e.cuda_available){r.value=`cpu`;let e=r.querySelector(`option[value="cuda"]`);e&&(e.disabled=!0)}e.comparison_available||(f=!1,i.disabled=!0,i.title=e.comparison_unavailable_reason||`Comparison runtime is unavailable.`,s&&(s.innerHTML=`<p class="error-msg">${e.comparison_unavailable_reason||`Comparison runtime is unavailable.`}</p>`),o&&(o.style.display=`block`))}catch(e){console.warn(`Could not fetch /api/capabilities:`,e)}function p(){let e=h(t.value);n.innerHTML=`
            <span>Words: ${e.words}</span>
            <span>Est. tokens: ${e.estimatedTokens.toLocaleString(`en-US`)}</span>
        `}function m(e){let n=l[e];n&&(t.value=n.prompt),p()}function g(){c&&=(c.close(),null),i.disabled=!f}function _(){g(),b(-1),d={},u=null,[`baselineMetrics`,`dflashMetrics`,`ccMetrics`].forEach(e=>{let t=document.getElementById(e);t&&(t.innerHTML=``)}),[`baselineResponse`,`dflashResponse`,`ccResponse`].forEach(e=>{let t=document.getElementById(e);t&&(t.textContent=`Waiting for comparison...`)}),[`baselineStatus`,`dflashStatus`,`ccStatus`].forEach(e=>y(e,`IDLE`)),[`baselineProgress`,`dflashProgress`,`ccProgress`].forEach(e=>{let t=document.getElementById(e);t&&(t.style.display=`none`)}),o&&(o.style.display=`none`),m(e.value||`gsm8k`)}async function C(){g();let e=t.value.trim();if(!e){t.focus();return}i.disabled=!0,o&&(o.style.display=`none`),b(0);try{let t=await fetch(`/api/compare`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({input:e,compression_device:r.value})});if(t.status===409){alert(`Server is busy with another comparison. Please wait and retry.`),i.disabled=!f;return}if(!t.ok){let e=await t.json().catch(()=>({detail:t.statusText}));alert(`Error starting job: `+(e.detail||t.statusText)),i.disabled=!f;return}let{job_id:n}=await t.json();d={},u=null,c=new EventSource(`/api/compare/`+n+`/events`),c.addEventListener(`input.parsed`,()=>{b(1)}),c.addEventListener(`condition.started`,e=>{let t;try{t=JSON.parse(e.data).condition_id}catch{t=e.data}if(t===`baseline-ar`){b(1),y(`baselineStatus`,`RUNNING`);let e=document.getElementById(`baselineProgress`);e&&(e.style.display=`block`)}else if(t===`dflash-r1`){b(2),y(`dflashStatus`,`RUNNING`);let e=document.getElementById(`dflashProgress`);e&&(e.style.display=`block`)}else{b(3),y(`ccStatus`,`RUNNING`);let e=document.getElementById(`ccProgress`);e&&(e.style.display=`block`)}}),c.addEventListener(`condition.completed`,e=>{let t;try{t=JSON.parse(e.data)}catch{return}d[t.condition_id]=t;let n,r,i,a;t.condition_id===`baseline-ar`?(n=`baselineStatus`,r=`baselineMetrics`,i=`baselineResponse`,a=`baselineProgress`,u=t.warm_request_e2e_ms):t.condition_id===`dflash-r1`?(n=`dflashStatus`,r=`dflashMetrics`,i=`dflashResponse`,a=`dflashProgress`):(n=`ccStatus`,r=`ccMetrics`,i=`ccResponse`,a=`ccProgress`),y(n,`DONE`);let o=document.getElementById(a);o&&(o.style.display=`none`);let s=document.getElementById(i);s&&(s.textContent=t.generated_text),v(r,t,u)}),c.addEventListener(`comparison.completed`,e=>{b(4);let t;try{t=JSON.parse(e.data)}catch{t=d}s&&(s.innerHTML=S(t)),o&&(o.style.display=`block`)}),c.addEventListener(`job.completed`,()=>{c.close(),c=null,i.disabled=!f}),c.addEventListener(`condition.failed`,e=>{let t;try{t=JSON.parse(e.data)}catch{t={error:e.data}}x(null,t.error||`Unknown error`)}),c.addEventListener(`job.failed`,e=>{let t;try{t=JSON.parse(e.data)}catch{t={error:e.data}}s&&(s.innerHTML=`<p class="error-msg">Job failed: ${t.error||`Unknown error`}</p>`),o&&(o.style.display=`block`),c&&=(c.close(),null),i.disabled=!f}),c.onerror=()=>{i.disabled&&=!f}}catch(e){console.error(`runComparison error:`,e),alert(`Network error: `+e.message),i.disabled=!f}}e.addEventListener(`change`,()=>m(e.value)),t.addEventListener(`input`,()=>{t.value!==(l[e.value]||{}).prompt&&(e.value=`custom`),p()}),i.addEventListener(`click`,C),a.addEventListener(`click`,_),_()}function w(){let e=[`def-yellow`,`def-cyan`,`def-hot`,`def-orange`,`def-purple`,`def-blue`,`def-green`,`def-cyan`,`def-hot`,`def-yellow`,`def-purple`,`def-orange`];document.getElementById(`metricDefs`).innerHTML=u.map(([t,n],r)=>`
        <article class="def-card ${e[r%e.length]}">
            <span class="metric-index">${String(r+1).padStart(2,`0`)}</span>
            <h3>${t}</h3>
            <p>${n}</p>
        </article>
    `).join(``)}var T={isMock:!0,throughput:{gsm8k:[{name:`Baseline-AR`,value:31},{name:`DFlash-R1`,value:113.7},{name:`LLMLingua-AR-R2`,value:30.5},{name:`CC-DFlash-R2`,value:100.9}],qmsum:[{name:`Baseline-AR`,value:24},{name:`DFlash-R1`,value:41.6},{name:`LLMLingua-AR-R2`,value:23.5},{name:`CC-DFlash-R2`,value:41.2}]},tokenReduction:{gsm8k:{oldPrompt:199,v5Prompt:163,afterSafeguard:161,promptCleanupPct:-18,llmlinguaReductionPct:-1.3},qmsum:{fullTranscript:12142,selectedContext:922,compressedContext:844,selectionReductionPct:92.4,llmlinguaReductionPct:8.5,overallReductionPct:93}},quality:{gsm8k:[{name:`Baseline-AR`,value:18,total:20},{name:`DFlash-R1`,value:18,total:20},{name:`LLMLingua-AR-R2`,value:18,total:20},{name:`CC-DFlash-R2`,value:18,total:20}],qmsum:[{name:`Baseline-AR`,value:.178},{name:`DFlash-R1`,value:.18},{name:`LLMLingua-AR-R2`,value:.179},{name:`CC-DFlash-R2`,value:.178}]},latency:{gsm8k:{dflash:{compression:0,prefill:87,generation:968,total:1055},ccdflash:{compression:92,prefill:84,generation:1008,total:1184},deltaMs:129,deltaPct:12.2},qmsum:{dflash:{compression:0,generationPipeline:2057,total:2057},ccdflash:{compression:466,generationPipeline:1954,total:2420},deltaMs:363,deltaPct:17.6}},kpi:{vram:`3.63 GiB`,acceptanceLength:`5.0`,compressionFallback:`0%`,parserFailures:0,emptyOutputs:0}};function E(e){let t=document.getElementById(`chart-throughput`);if(!t)return;let n=T.throughput[e],r=Math.max(...n.map(e=>e.value))*1.1;t.innerHTML=`
        <div class="plot-frame">
            <div class="bar-chart bar-chart--vertical">
                ${n.map(e=>{let t=``;return e.name.includes(`DFlash-R1`)&&(t=`highlight-cyan`),e.name.includes(`CC-DFlash-R2`)&&(t=`highlight-magenta`),`
                    <div class="bar-col">
                        <div class="bar-val">${e.value.toFixed(1)}</div>
                        <div class="bar-track">
                            <div class="bar-fill ${t}" style="height: ${e.value/r*100}%"></div>
                        </div>
                        <div class="bar-label">${e.name.replace(`-R`,`
-R`)}</div>
                    </div>
                    `}).join(``)}
            </div>
        </div>
    `}function D(e){let t=document.getElementById(`chart-reduction`),n=document.getElementById(`note-reduction`);if(!(!t||!n))if(e===`gsm8k`){let e=T.tokenReduction.gsm8k,r=Math.abs(e.promptCleanupPct),i=Math.abs(e.llmlinguaReductionPct),a=Math.abs((e.afterSafeguard-e.oldPrompt)/e.oldPrompt*100).toFixed(1);t.innerHTML=`
            <div class="plot-frame">
                <div class="token-flow">
                    <div class="tf-stage">
                        <div class="tf-label">ORIGINAL</div>
                        <div class="tf-value">${e.oldPrompt}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Old prompt</div>
                    </div>
                    <div class="tf-arrow">
                        <div class="tf-arrow-icon">→</div>
                        <div class="tf-chip">-${r}%<span>Prompt cleanup</span></div>
                    </div>
                    <div class="tf-stage bg-cyan">
                        <div class="tf-label">PROMPT V5</div>
                        <div class="tf-value">${e.v5Prompt}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Shared instruction</div>
                    </div>
                    <div class="tf-arrow">
                        <div class="tf-arrow-icon">→</div>
                        <div class="tf-chip bg-yellow">-${i}%<span>LLMLingua</span></div>
                    </div>
                    <div class="tf-stage bg-yellow">
                        <div class="tf-label">SAFEGUARDED</div>
                        <div class="tf-value">${e.afterSafeguard}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Compressed input</div>
                    </div>
                </div>
                <div class="tf-overall">
                    OVERALL: ${e.oldPrompt} → ${e.afterSafeguard} TOKENS &middot; -${a}%
                </div>
            </div>
        `,n.innerHTML=`SHORT PROMPT: PHẦN GIẢM CHÍNH ĐẾN TỪ PROMPT CLEANUP.`}else{let e=T.tokenReduction.qmsum,r=Math.abs(e.selectionReductionPct).toFixed(1),i=Math.abs(e.llmlinguaReductionPct).toFixed(1),a=Math.abs(e.overallReductionPct).toFixed(1);t.innerHTML=`
            <div class="plot-frame">
                <div class="token-flow">
                    <div class="tf-stage">
                        <div class="tf-label">FULL</div>
                        <div class="tf-value">${e.fullTranscript.toLocaleString()}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Full transcript</div>
                    </div>
                    <div class="tf-arrow">
                        <div class="tf-arrow-icon">→</div>
                        <div class="tf-chip">-${r}%<span>Context selection</span></div>
                    </div>
                    <div class="tf-stage bg-cyan">
                        <div class="tf-label">SELECTED</div>
                        <div class="tf-value">${e.selectedContext.toLocaleString()}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Query-aware context</div>
                    </div>
                    <div class="tf-arrow">
                        <div class="tf-arrow-icon">→</div>
                        <div class="tf-chip bg-yellow">-${i}%<span>LLMLingua</span></div>
                    </div>
                    <div class="tf-stage bg-magenta">
                        <div class="tf-label">COMPRESSED</div>
                        <div class="tf-value">${e.compressedContext.toLocaleString()}</div>
                        <div class="tf-unit">TOKENS</div>
                        <div class="tf-sub">Target input</div>
                    </div>
                </div>
                <div class="tf-overall bg-purple">
                    OVERALL: ${e.fullTranscript.toLocaleString()} → ${e.compressedContext.toLocaleString()} TOKENS &middot; -${a}%
                </div>
            </div>
        `,n.innerHTML=`LONG CONTEXT: PHẦN GIẢM CHÍNH ĐẾN TỪ QUERY-AWARE SELECTION.`}}function O(e){let t=document.getElementById(`chart-quality`),n=document.getElementById(`note-quality`);if(!(!t||!n))if(e===`gsm8k`)t.innerHTML=`
            <div class="plot-frame" style="padding: 0;">
                <div class="panel">
                    <h4>GSM8K — Numeric Exact Match</h4>
                    <div class="quality-bars">
                        ${T.quality.gsm8k.map(e=>`
                            <div class="q-row">
                                <span class="q-label">${e.name}</span>
                                <div class="q-track">
                                    <div class="q-seg filled" style="width: ${e.value/e.total*100}%"></div>
                                    <div class="q-seg" style="width: ${(e.total-e.value)/e.total*100}%"></div>
                                </div>
                                <span class="q-val">${e.value}/${e.total}</span>
                            </div>
                        `).join(``)}
                    </div>
                </div>
            </div>
        `,n.innerHTML=`Compression giữ quality ngang target baseline trong thiết lập mock.`;else{let e=T.quality.qmsum,r=.17;t.innerHTML=`
            <div class="plot-frame" style="padding: 0;">
                <div class="panel">
                    <h4>QMSum — Lexical Overlap Proxy</h4>
                    <div class="quality-bars">
                        ${e.map(e=>`
                            <div class="q-row">
                                <span class="q-label">${e.name}</span>
                                <div class="q-track"><div class="q-fill" style="width: ${(e.value-r)/(.185-r)*100}%"></div></div>
                                <span class="q-val">${e.value.toFixed(3)}</span>
                            </div>
                        `).join(``)}
                    </div>
                </div>
            </div>
        `,n.innerHTML=`Lexical diagnostic proxy — không đại diện cho semantic correctness.`}}function k(e){let t=document.getElementById(`chart-latency`),n=t?.nextElementSibling;if(!t)return;let r=T.latency[e];if(e===`gsm8k`){let e=Math.max(r.dflash.total,r.ccdflash.total)*1.1;t.innerHTML=`
            <div class="plot-frame">
                <div class="latency-legend">
                    <span class="leg-item"><span class="leg-box leg-comp"></span> Compression</span>
                    <span class="leg-item"><span class="leg-box leg-prefill"></span> Prefill</span>
                    <span class="leg-item"><span class="leg-box leg-gen"></span> Generation</span>
                </div>
                <div class="stacked-bars">
                    <div class="st-row">
                        <span class="st-label">DFlash-R1</span>
                        <div class="st-track">
                            <div class="st-seg st-prefill" style="width: ${r.dflash.prefill/e*100}%"></div>
                            <div class="st-seg st-gen" style="width: ${r.dflash.generation/e*100}%"></div>
                        </div>
                        <span class="st-val">${r.dflash.total} ms</span>
                    </div>
                    <div class="st-row">
                        <span class="st-label">CC-DFlash-R2</span>
                        <div class="st-track">
                            <div class="st-seg st-comp" style="width: ${r.ccdflash.compression/e*100}%"></div>
                            <div class="st-seg st-prefill" style="width: ${r.ccdflash.prefill/e*100}%"></div>
                            <div class="st-seg st-gen" style="width: ${r.ccdflash.generation/e*100}%"></div>
                        </div>
                        <span class="st-val">${r.ccdflash.total} ms</span>
                    </div>
                </div>
                <div class="latency-delta-wrap"><div class="latency-delta">+${r.deltaMs} ms (+${r.deltaPct}%) slower</div></div>
            </div>
        `}else{let e=Math.max(r.dflash.total,r.ccdflash.total)*1.1;t.innerHTML=`
            <div class="plot-frame">
                <div class="latency-legend">
                    <span class="leg-item"><span class="leg-box leg-comp"></span> Compression</span>
                    <span class="leg-item"><span class="leg-box leg-gen"></span> Generation Pipeline</span>
                </div>
                <div class="stacked-bars">
                    <div class="st-row">
                        <span class="st-label">DFlash-R1</span>
                        <div class="st-track">
                            <div class="st-seg st-gen" style="width: ${r.dflash.generationPipeline/e*100}%"></div>
                        </div>
                        <span class="st-val">${r.dflash.total} ms</span>
                    </div>
                    <div class="st-row">
                        <span class="st-label">CC-DFlash-R2</span>
                        <div class="st-track">
                            <div class="st-seg st-comp" style="width: ${r.ccdflash.compression/e*100}%"></div>
                            <div class="st-seg st-gen" style="width: ${r.ccdflash.generationPipeline/e*100}%"></div>
                        </div>
                        <span class="st-val">${r.ccdflash.total} ms</span>
                    </div>
                </div>
                <div class="latency-delta-wrap"><div class="latency-delta">+${r.deltaMs} ms (+${r.deltaPct}%) slower</div></div>
            </div>
        `}n&&n.classList.contains(`evidence-note`)&&(n.innerHTML=`Decode can improve while end-to-end still loses to compression overhead.`)}function A(){let e=document.getElementById(`kpi-strip`);if(!e)return;let t=T.kpi;e.innerHTML=`
        <div class="kpi-card">
            <div class="kpi-val">${t.vram}</div>
            <div class="kpi-label">Peak Reserved VRAM</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val">${t.acceptanceLength} <span class="kpi-badge">diagnostic</span></div>
            <div class="kpi-label">Mean Acceptance Length τ</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val">${t.compressionFallback}</div>
            <div class="kpi-label">Compression Fallback</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val">${t.parserFailures}</div>
            <div class="kpi-label">Parser Failures</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-val">${t.emptyOutputs}</div>
            <div class="kpi-label">Empty Outputs</div>
        </div>
    `}function j(){document.querySelectorAll(`.card-toggles`).forEach(e=>{let t=e.querySelectorAll(`.tgl-btn`);t.forEach(e=>{e.addEventListener(`click`,e=>{t.forEach(e=>e.classList.remove(`active`)),e.target.classList.add(`active`);let n=e.target.dataset.ds,r=e.target.closest(`.evidence-card`);r.id===`card-throughput`&&E(n),r.id===`card-reduction`&&D(n),r.id===`card-quality`&&O(n),r.id===`card-latency`&&k(n)})})})}function M(){E(`gsm8k`),D(`gsm8k`),O(`gsm8k`),k(`qmsum`),A(),j()}function N(){let e=[...document.querySelectorAll(`.nav a[href^="#"]`)],t=e.map(e=>document.querySelector(e.getAttribute(`href`))).filter(Boolean),n=new IntersectionObserver(t=>{let n=t.filter(e=>e.isIntersecting).sort((e,t)=>t.intersectionRatio-e.intersectionRatio)[0];n&&e.forEach(e=>{e.classList.toggle(`active`,e.getAttribute(`href`)===`#${n.target.id}`)})},{rootMargin:`-25% 0px -60% 0px`,threshold:[.05,.2,.5]});t.forEach(e=>n.observe(e))}f(),C(),w(),M(),N(),document.addEventListener(`DOMContentLoaded`,()=>{let e=document.getElementById(`minimap`);if(!e)return;let t=e.querySelectorAll(`.minimap-marker`),n=null;t.forEach(e=>{e.addEventListener(`pointerenter`,()=>{n&&=(clearTimeout(n),null),t.forEach(t=>{t!==e&&t.classList.remove(`is-hovered`)}),e.classList.add(`is-hovered`)}),e.addEventListener(`pointerleave`,()=>{n=setTimeout(()=>{e.classList.remove(`is-hovered`)},150)}),e.addEventListener(`click`,()=>{let t=e.getAttribute(`data-target`),n=document.getElementById(t);if(n){let t=window.matchMedia(`(prefers-reduced-motion: reduce)`).matches;n.scrollIntoView({behavior:t?`auto`:`smooth`}),e.classList.remove(`is-hovered`)}})});let r=new IntersectionObserver(e=>{e.forEach(e=>{if(e.isIntersecting){let n=e.target.getAttribute(`id`);t.forEach(e=>{e.getAttribute(`data-target`)===n?e.classList.add(`active`):e.classList.remove(`active`)})}})},{root:null,rootMargin:`-30% 0px -70% 0px`,threshold:0});t.forEach(e=>{let t=e.getAttribute(`data-target`),n=document.getElementById(t);n&&r.observe(n)})});