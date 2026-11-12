# Novelty check

Date: 2026-11-12. Status: draft, waiting for approval. References are recorded with full metadata and read depth in `paper/refs_verified.md`.

## Verdict

The expected gap holds, but it is narrower than the brief assumes. In the searches described below I found no work that does all four of the following together:

1. A controlled comparison on the same applicants of an LLM that decides (A), an LLM that only extracts fields for a trained scorecard (B), and B plus code-level validation and review triggers (C).
2. In a lending setting, with attack success defined against the decision a clean tabular scorecard would make.
3. With open-weight models between about 1.5B and 8B parameters, including a size comparison.
4. Measuring the residual attack surface from extraction manipulation (falsified values with no instruction text) and how much validation and review recover, with the review-workload cost.

Each ingredient has precedent. Instruction injection in underwriting has a benchmark (PIBench). Hidden data injection without instructions has been measured in real resumes (Zhang et al.). Architectural separation has been proposed and argued qualitatively (Design Patterns, CaMeL). What is missing is the controlled measurement that puts these together. The contribution is that combination and the lending measurement. The study introduces no new attack, defense or vulnerability class.

## Search method and limits

- Web search: 13 queries covering underwriting, credit and loan injection, the named candidate works, dual-LLM and plan-then-execute patterns, extraction architectures, resume screening, MCP studies, adversarial robustness in credit, and Kaggle quotas.
- arXiv API keyword searches (abstract field, newest first): injection with underwriting, lending, loan or credit; injection with structured output and extraction; injection with payslip, bank statement, KYC or invoice; injection with "quarantined". They returned 3, 0, 3 and 6 papers, none of which does the comparison above.
- Full texts opened for the works closest to the claim (see each entry for depth).
- Limits. The web search tool is US-only and returns snippets. The arXiv API searches abstracts only. I did not query Semantic Scholar, Google Scholar, SSRN, the ACM Digital Library or conference sites, and I did not search for peer-reviewed work in credit-risk journals. New preprints appear weekly, so this check has to be repeated just before submission.

## Related work

### Lending

**PIBench** (Roelofs, Schmitt, Eber, Taktile Labs, web page, June 2026).
- Summary: a hand-authored benchmark of prompt injection against an agentic underwriting workflow. 78 cases (53 injections, 25 benign), five injection vectors (invocation message, structured input, uploaded documents, file names, tool responses), four methods (instruction override, jailbreak, context manipulation, delimiter exploitation), 16 frontier models from three providers, scored with and without untrusted-content tagging. The page reports average defense success of 93.2% without tagging and 97.7% with it, and says the residual risk is concentrated in sophisticated injections inside uploaded documents.
- Covers: architecture A with a tagging defense in a lending workflow, benign cases for false positives, sophistication levels. Its high-sophistication cases include forged third-party reports that issue no command and offer a credible mitigating narrative, which is close in spirit to our category 5.
- Does not cover: any architecture other than the LLM deciding; open-weight small models (I did not read the per-model results, so I cannot rule out that some appear); a scorecard-grounded definition of harm on real tabular data; extraction manipulation as a separately measured residual; human-review triggers. It is a vendor-authored web page and has not been peer reviewed.
- Read depth: introduction to the start of the results section.

**Snyk demonstration** (Snyk, web article, 2025-05-07).
- Summary: a credit-score app where white text in a PDF changed an LLM-generated score.
- Covers: a single demonstration that architecture A fails in a credit setting.
- Does not cover: measurement, defenses, any alternative architecture. Motivation only.

### Document-borne injection in hiring

**Zhang et al.** (USENIX Security 2026, arXiv 2605.28999).
- Summary: measurement over about 200,000 real resumes from one vendor, with two purpose-built detectors. The paper reports that over 90% of injected prompts contain only data and no explicit instruction, for example concealed skill lists or fabricated experience, aimed at downstream steps such as keyword matching.
- Covers: real-world prevalence and strategy of hidden injection, including data-only injection, in a document-screening application.
- Does not cover: lending, a controlled architecture comparison, or defenses by architecture. I read the abstract and introduction passages. I have not checked whether the paper measures outcome changes, so I make no claim either way.

**ResumeShield** (Barach, arXiv 2609.20188, 24 July 2026, single author).
- Summary: a four-stage defense for resume screening (three filtering stages and an application-layer data fence) with a seeded synthetic benchmark of 104 documents. The abstract reports that the fence alone removes all measured attack success while filtering alone leaves 16.7% effective.
- Covers: channel separation at the application layer, an adaptive-payload family, an ablation. It cites Zhang et al. for the observation that fabricated qualifications can work better than instructions when pipelines parse resumes into fields.
- Does not cover: extractor-plus-scorecard decisions, lending, or measurement of falsified visible claims (it lists those as future work). The data fence is closer to tagging than to architecture B.
- Read depth: abstract through positioning. Results tables not read.

**Akdemir and Levy** (RecSys in HR 2025, CEUR Vol-4046).
- Summary: injection against an LLM that labels how well a resume meets job criteria. 10 instruction-style injection strings, 5 OpenAI models, 24 prompting and defense variants, 1,200 experiments, 1,564 job and resume pairs. The introduction says that some mitigation combinations reach 100% robustness against the strings tested.
- Covers: an LLM acting as a feature extractor or labeler, and prompt-level mitigations (untrusted-content tags, guardrail text, message placement, output format).
- Does not cover: a deterministic downstream scorer, validation or review rules, falsified values without instruction text, lending, open-weight models. All models are hosted OpenAI models.
- Read depth: pages 1 to 4. Results not read.

### Architectural defenses

**Design Patterns for Securing LLM Agents** (Beurer-Kellner et al., arXiv 2506.08837).
- Summary: six patterns (action-selector, plan-then-execute, LLM map-reduce, dual LLM, code-then-execute, context-minimization) analysed through ten case studies, including a resume-screening assistant with four candidate designs.
- Covers: the design vocabulary that architectures B and C instantiate. Our B corresponds to the quarantined-extractor half of the dual LLM and map-reduce patterns, with a trained scorecard in place of a privileged LLM.
- Does not cover: any measured attack success rate. The full text contains no occurrence of "attack success" or "ASR". The analysis is qualitative. It also does not treat lending.

**CaMeL** (Debenedetti et al., arXiv 2503.18813).
- Summary: a system layer that extracts control and data flow from the user query and enforces capability policies, evaluated on AgentDojo.
- Covers: provable control-flow and data-flow protection for tool-using agents.
- Does not cover: manipulation of values that do not alter control or data flow. Section 3.1 lists as an explicit non-goal "text-to-text attacks which have no consequences on the data flow". Falsified extracted fields in a scorecard pipeline are an analogous case, so CaMeL gives no guarantee about the residual RQ2 measures. Tool-use agents, not underwriting.

**PACT** (Fan et al., arXiv 2605.11039) and **Certified Multi-Source Integrity** (Pandey et al., arXiv 2609.34245).
- Summary: PACT tracks provenance of tool arguments and checks each against a trust contract on AgentDojo. Pandey et al. certify structured actions field by field using corroboration across independent evidence, measured on sanctions designations and software supply-chain provenance, plus a real agent loop across five models.
- Covers: field-level integrity checks and corroboration, the same idea as the cross-document checks in C.
- Does not cover: lending, a trained scorecard as decider, or a comparison with LLM-as-decider. Abstracts only.

### Prompt-level defenses and their evaluation

- **Spotlighting** (Hines et al.) and **Instruction Hierarchy** (Wallace et al.): the source of the tagging and system-prompt defenses used as the A-variant comparison point. Metadata only.
- **The Attacker Moves Second** (Nasr et al.): adaptive attacks bypass 12 recent defenses against jailbreaks and prompt injection, most of which had reported near-zero attack success. It supports the premise that in-prompt defenses are weak, and it is the reason the Limitations section has to say we test a fixed attack set and no adaptive attacker.
- **Indirect prompt injection** (Greshake et al.): the foundational threat description.

### Other works from the brief

- **MCPTox** (AAAI 2026) and the two MCP client studies (Huang et al., 2026): all concern poisoned tool descriptions and tool metadata in MCP deployments. That surface is separate from applicant-supplied documents. I recommend at most one clause of context in the paper, or dropping them.
- **Strategic Classification** (Hardt et al.): the classical framing of agents who change their features to flip a classifier. Relevant to RQ2, see the next section.
- **CONSTRUCT** (Goh and Mueller): per-field trust scores for LLM structured output. A possible alternative to hand-written review triggers, for the discussion only.
- **FinVault**: excluded, see `paper/refs_verified.md`.

## What this study adds

1. A controlled A versus B versus C comparison on identical applicants, attacks and models. PIBench evaluates A with and without tagging. ResumeShield evaluates a filter and fence against a naive pipeline. The design-pattern literature argues for B-like designs without measuring them.
2. A ground truth for harm that comes from a trained scorecard on 150,000 real tabular records, with documents generated to match each row. PIBench cases are hand-authored with an expected non-approve verdict.
3. A measurement of the extraction-manipulation residual under a deterministic decider, and of how much cross-field checks and code-defined review triggers recover at what review-rate cost. Prior work names this attack (Zhang et al. in the wild, ResumeShield and CaMeL as out of scope) without measuring it in lending.
4. Open-weight models of 1.5B to 8B with a size comparison, where the closest benchmarks use hosted frontier or OpenAI models.

## Claims to soften, and design points this check raises

**1. Do not call anything first or novel.** The brief already restricts these words. The evidence above supports a narrower sentence: to our knowledge, no prior study compares these three architectures in lending with open-weight models. That sentence needs the repeat search before submission.

**2. RQ2 is classical document fraud seen through an LLM.** A raised income figure is application fraud, and feature manipulation against fixed classifiers is the subject of strategic classification. H2 (non-zero ASR from falsified values) will hold almost automatically whenever the scorecard is sensitive to the falsified field and the falsification is large enough. The informative quantity is the difference between ASR with the LLM extractor and ASR with a perfect extractor reading the same falsified document. That difference separates what the LLM adds from what any pipeline suffers when a document lies. I propose adding an **oracle-extractor reference arm** to B and C. It costs almost no compute, since it reads the falsified value straight from the generator. This is a design change to the brief and needs Craig's decision.

**3. ASR as defined can credit attacks with the LLM's own errors.** The brief defines ASR among applicants whom the clean scorecard would decline or refer, as the share approved under attack. Architecture A may already approve some of them with clean input, because a small LLM is a worse scorer than the scorecard. That share is not caused by the attack. I propose reporting the raw ASR from the brief as the primary metric and, beside it, the paired flip rate (same architecture, same applicant, not approve when clean and approve when attacked), with the clean approve rate as its own row. The choice changes the numbers, so it belongs in the preregistration before any run.

**4. Single-document and consistent falsification are different attacks.** An income raised on the payslip alone contradicts the bank statement, and the cross-document check in C catches it by construction. An attacker who raises the value consistently on every document defeats that check. The preregistration should state which variants are in the set. I recommend both, labelled separately, because otherwise C's headline result depends on an unstated choice.

**5. H1 needs a closer look.** Under B an instruction-style payload has no direct path to the decision. It can still steer the extractor into emitting a wrong field. The analysis should record, for every successful attack under B, whether the changed field traces to instruction text or to a content change, using the category labels from the preregistration.

## Decisions needed from Craig

1. Approve the narrowed framing in the Verdict and in claim 1 above.
2. Add the oracle-extractor arm (point 2)? Recommended yes.
3. Primary ASR: the brief's raw definition with the paired flip rate reported beside it (point 3)? Recommended yes.
4. Include both single-document and consistent-falsification variants (point 4)? Recommended yes.
5. Drop the MCP works from related work, or keep one clause? Recommended drop.
6. Author name on the paper and the CITATION file. The brief says "Craig Ouma". Earlier papers, the git configuration and the Kaggle profile use "Craig Carlos Ouma".
