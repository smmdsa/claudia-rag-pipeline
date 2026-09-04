/**
 * research — a 3-layer read-only research harness. No edits.
 *
 *   layer 1  ants      many small agents. One atomic question each. They return RAW
 *                      data: file:line plus a snippet. No conclusion.
 *   layer 2  bees      few agents. Composite traces over the ant evidence. They read
 *                      function bodies and give a verdict per section.
 *   layer 3  reviewer  one agent. It audits the plan that the bees propose against
 *                      the ant evidence, names anti-patterns, and approves or adjusts.
 *   top      the main loop consolidates, closes the gaps, and runs the plan.
 *
 * args = {
 *   question:      string                  the big question (a label)
 *   repoNote?:     string                  the return contract (override)
 *   antQuestions:  string[]                REQUIRED, one or more
 *   beeTasks?:     Array<{ key, prompt }>  optional
 *   antModel?:     string                  default 'haiku'
 *   beeModel?:     string                  default 'sonnet'
 *   reviewer?:     boolean                 default true when bees exist
 *   reviewerModel?: string                 default 'opus'
 *   chaseGaps?:    boolean                 default true: a second round of ants on the bee gaps
 *   gapCap?:       number                  default 6
 * }
 *
 * Returns { question, ants, unanswered, bees, antsRound2, reviewer }.
 * An ant that returns nothing is DECLARED in `unanswered`. Silence is not "nothing there".
 */
export const meta = {
  name: 'research',
  description: '3-layer read-only research: ants gather file:line evidence, bees trace flows, one reviewer audits the plan.',
  whenToUse: 'Before a non-trivial change: map relations, trace flows, check the premises of a plan. Parameterised by antQuestions and beeTasks.',
  phases: [
    { title: 'Ants', detail: 'atomic questions, file:line plus snippet, with one retry' },
    { title: 'Bees', detail: 'composite traces over the ant evidence' },
    { title: 'Gaps', detail: 'a second round of ants on the gaps that the bees declared' },
    { title: 'Reviewer', detail: 'audit of the plan against the evidence' },
  ],
}

const ANT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    question: { type: 'string' },
    refs: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          file: { type: 'string' },
          line: { type: 'number' },
          snippet: { type: 'string', description: 'verbatim, 4 lines or fewer' },
          note: { type: 'string', description: 'one tag: emitter|subscriber|definition|caller|dead' },
        },
        required: ['file', 'snippet'],
      },
    },
    verdict: { type: 'string', description: 'one or two sentences, evidence only' },
  },
  required: ['question', 'refs', 'verdict'],
}

const BEE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    subsystem: { type: 'string' },
    flow: { type: 'array', items: { type: 'string' }, description: 'ordered steps, each with file:line' },
    findings: { type: 'string', description: 'synthesis grounded in the evidence' },
    race_or_timing: { type: 'string' },
    migration_impact: { type: 'string', description: 'what holds and what breaks under the proposed change' },
    gaps: { type: 'array', items: { type: 'string' }, description: 'open questions to close before a plan' },
  },
  required: ['subsystem', 'findings'],
}

const REVIEWER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verdict: { type: 'string', enum: ['approve', 'approve_with_adjustments', 'reject'] },
    architecture_assessment: { type: 'string' },
    pattern_risks: { type: 'array', items: { type: 'string' } },
    correctness_gaps: { type: 'array', items: { type: 'string' } },
    adjustments: { type: 'array', items: { type: 'string' }, description: 'each with file:line' },
    green_light: { type: 'string', description: 'the ordered steps to implement' },
  },
  required: ['verdict', 'architecture_assessment', 'green_light'],
}

const DEFAULT_REPO_NOTE =
  'Read-only research: NO edits. Return ONLY evidence: file:line plus a verbatim snippet of 4 lines or fewer. ' +
  'Do NOT speculate beyond what the code shows. Use the mcp__qmd__* index tools first when they answer; ' +
  'then Grep, Glob, and Read across the whole repository. If the index is down, say so.'

let a = (args && typeof args === 'object') ? args : {}
if (typeof args === 'string' && args.trim()) {
  try { const parsed = JSON.parse(args); if (parsed && typeof parsed === 'object') a = parsed } catch { /* keep {} */ }
}
const repoNote = a.repoNote || DEFAULT_REPO_NOTE
const antQuestions = Array.isArray(a.antQuestions) ? a.antQuestions.filter((q) => typeof q === 'string' && q.trim()) : []
const beeTasks = Array.isArray(a.beeTasks) ? a.beeTasks.filter((t) => t && typeof t.prompt === 'string' && t.prompt.trim()) : []
const antModel = a.antModel || 'haiku'
const beeModel = a.beeModel || 'sonnet'
const reviewerModel = a.reviewerModel || 'opus'

if (antQuestions.length === 0) {
  throw new Error('research: args.antQuestions must be a non-empty array of strings.')
}

if (a.question) log(`question: ${a.question}`)

phase('Ants')

const ant = (q, i, label) => agent(`${repoNote}\n\nMICRO-QUESTION #${i + 1}: ${q}`, {
  label, phase: 'Ants', schema: ANT_SCHEMA, agentType: 'researcher', model: antModel, effort: 'low',
})

const antResults = await parallel(antQuestions.map((q, i) => () => ant(q, i, `ant#${i + 1}`)))
const slots = antQuestions.map((q, i) => ({ q, i, res: antResults[i] || null }))
const failed = slots.filter((s) => !s.res)
if (failed.length > 0) {
  log(`ants: ${failed.length} without an answer. One retry.`)
  const retry = await parallel(failed.map((s) => () => ant(s.q, s.i, `ant#${s.i + 1}:retry`)))
  failed.forEach((s, k) => { s.res = retry[k] || null; if (!s.res) log(`ant #${s.i + 1} LOST after the retry: "${s.q}"`) })
}
const ants = slots.filter((s) => s.res).map((s) => s.res)
const unanswered = slots.filter((s) => !s.res).map((s) => s.q)
log(`ants: ${ants.length}/${antQuestions.length} returned data`)

if (beeTasks.length === 0) {
  return { question: a.question || null, ants, unanswered, bees: [], antsRound2: [], reviewer: null }
}

const antDigest = JSON.stringify(ants, null, 1)

phase('Bees')

const beeResults = await parallel(beeTasks.map((t, i) => () =>
  agent(
    `${repoNote}\n\nYou are a mid-layer synthesizer. Below is RAW evidence that atomic agents collected ` +
    `(file:line plus snippets). Use it as your map, then READ the relevant function bodies. Check before you ` +
    `trust. FLAG any ant claim that the code contradicts.\n\n=== ANT EVIDENCE (JSON) ===\n${antDigest}\n=== END ===\n\n` +
    `YOUR COMPOSITE TASK (${t.key || `bee#${i + 1}`}):\n${t.prompt}`,
    { label: `bee:${t.key || i + 1}`, phase: 'Bees', schema: BEE_SCHEMA, agentType: 'researcher', model: beeModel, effort: 'medium' }
  )))
const bees = beeResults.filter(Boolean)
log(`bees: ${bees.length}/${beeTasks.length} returned a synthesis`)

const GAP_CAP = Number.isFinite(a.gapCap) ? a.gapCap : 6
const rawGaps = bees.flatMap((b) => (Array.isArray(b.gaps) ? b.gaps : [])).filter((g) => typeof g === 'string' && g.trim())
const uniqueGaps = [...new Set(rawGaps.map((g) => g.trim()))]
const gapsToChase = a.chaseGaps === false ? [] : uniqueGaps.slice(0, GAP_CAP)
if (uniqueGaps.length > gapsToChase.length) {
  log(`gaps: ${uniqueGaps.length - gapsToChase.length} NOT chased (cap ${GAP_CAP}): ${uniqueGaps.slice(GAP_CAP).join(' · ')}`)
}

let antsRound2 = []
if (gapsToChase.length > 0) {
  phase('Gaps')
  const gapResults = await parallel(gapsToChase.map((g, i) => () =>
    agent(`${repoNote}\n\nThis is a GAP that a synthesizer flagged after it read the code. Close it with evidence only.\n\nGAP #${i + 1}: ${g}`,
      { label: `gap#${i + 1}`, phase: 'Gaps', schema: ANT_SCHEMA, agentType: 'researcher', model: antModel, effort: 'low' })))
  antsRound2 = gapResults.filter(Boolean)
  log(`gaps: ${antsRound2.length}/${gapsToChase.length} closed with evidence`)
}

const reviewerEnabled = a.reviewer !== false && bees.length > 0
if (!reviewerEnabled) {
  return { question: a.question || null, ants, unanswered, bees, antsRound2, reviewer: null }
}

phase('Reviewer')

const reviewerPrompt =
  'Read-only architectural review: NO edits (Read, Grep, Glob only).\n\n' +
  'You are the most senior reviewer and the FINAL gate before any code is written. The bees proposed a plan; ' +
  'the ants gathered the raw evidence. Your job is an ADVERSARIAL review of the plan, not more synthesis.\n' +
  '  1. Detect anti-patterns: god object, hidden coupling, leaky ownership, order-of-operations hazard, ' +
  'dual dispatch or race window, YAGNI plumbing, broken single source of truth.\n' +
  '  2. Judge the architecture: cohesion, coupling, testability, deletion-friendliness, whether the change ' +
  'LOWERS total complexity.\n' +
  '  3. CHECK, do not rubber-stamp: open the code at any cited file:line you doubt, and flag what the code contradicts.\n' +
  '  4. Deliver a verdict with concrete adjustments (each with file:line) and the correctness gaps to close first. ' +
  'Leave an ordered execution note.\n\n' +
  `=== BIG QUESTION ===\n${a.question || '(unspecified)'}\n\n` +
  `=== ANT EVIDENCE (JSON) ===\n${antDigest}\n=== END ===\n\n` +
  (antsRound2.length ? `=== GAP-CLOSING EVIDENCE ===\n${JSON.stringify(antsRound2, null, 1)}\n=== END ===\n\n` : '') +
  (unanswered.length ? `=== BLIND SPOTS (no data came back; treat as UNKNOWN) ===\n${unanswered.map((q) => `- ${q}`).join('\n')}\n=== END ===\n\n` : '') +
  `=== BEE SYNTHESES / PROPOSED PLAN (JSON) ===\n${JSON.stringify(bees, null, 1)}\n=== END ===`

const reviewer = await agent(reviewerPrompt, {
  label: `reviewer:${reviewerModel}`, phase: 'Reviewer', schema: REVIEWER_SCHEMA, agentType: 'Plan', model: reviewerModel, effort: 'high',
})
log(`reviewer: verdict = ${reviewer?.verdict ?? 'no answer'}`)

return { question: a.question || null, ants, unanswered, bees, antsRound2, reviewer: reviewer || null }
