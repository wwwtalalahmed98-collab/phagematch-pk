# Building an in-silico phage cocktail design tool for Pakistan

**A staged build plan.** Written 17 Aug 2026, after completing the *Klebsiella*
capsule coverage study.

The goal, as stated: a tool a phage researcher would run before spending money in
the wet lab, to decide whether a candidate cocktail is likely to work against a
given isolate — specialised for the Pakistani setting.

This document says what to build, in what order, what already exists so you do not
rebuild it, and how each stage gets validated. Effort estimates assume one student
working part-time on an i5-8350U with 8 GB RAM, no Docker, no local cluster.

---

## 0. Scope the claim before writing any code

Three different products get called "a phage prediction tool". They need different
data and carry very different risk:

| Product | Question answered | Feasible now? |
|---|---|---|
| **A. Coverage map** | Which capsule types circulating here have any phage at all? | **Done** — this is the current manuscript |
| **B. Isolate to phage match** | Given this isolate's genome, which known phages should lyse it? | Partly solved by others; extendable |
| **C. Cocktail design** | Which *set* of phages minimises resistance emergence for this isolate or population? | **Open problem — this is the real gap** |

Build B on top of what exists, and make **C** the contribution. Do not describe the
tool as personalised medicine until it has been tested against isolates it has
never seen.

---

## 1. Prior art — what you must not rebuild

Check each of these before writing a line of code. Two afternoons here saves months.

**PhageHostLearn** — Boeckaerts *et al.*, *Nat Commun* 2024;**15**:4355,
doi:10.1038/s41467-024-48675-6. Machine-learning prediction of **strain-level**
*Klebsiella* phage–host interactions from phage receptor-binding proteins and
bacterial receptors. Cross-validated ROC AUC up to 81.8%, and — unusually — they
validated it in the laboratory on the real task of finding phages for given strains.

This is your product B, for your organism, already built and lab-validated by a
group at Ghent. **Treat it as a dependency and a baseline, not a competitor.**
Anything you build must beat it or do something it does not.

Other components that already exist and should be imported rather than written:

| Need | Tool | Notes |
|---|---|---|
| Capsule / O typing | **Kaptive 3**, **Kleborate 3** | already in your pipeline |
| Phage genome corpus | **INPHARED** (Millard lab), **PhageScope** | curated, versioned, regularly updated |
| Anti-phage defence systems | **DefenseFinder**, **PADLOC** | detect RM, BREX, Abi, retrons, CBASS from an assembly |
| CRISPR arrays and spacers | **CRISPRCasFinder**, **CRISPRDetect** | spacers record past phage encounters directly |
| Prophage detection | **PhiSpy**, **geNomad**, **VIBRANT** | needed to exclude temperate phages on safety grounds |
| Lifestyle, lytic vs temperate | **BACPHLIP** | a therapeutic cocktail must be strictly lytic |
| RBP structure | **ESMFold**, **AlphaFold DB** | ESMFold is lighter and runs on Colab |

---

## 2. The actual gap

PhageHostLearn predicts whether **one phage** infects **one strain** from receptor
compatibility. What no available tool does well:

1. **Defence-system awareness.** A phage can bind the capsule perfectly and still
   fail because the host carries a restriction–modification system or a CRISPR
   spacer matching that phage. Receptor match is necessary, not sufficient.
2. **Cocktail composition.** Choosing 3–5 phages whose receptors do *not* overlap,
   so a single capsule mutation cannot escape the whole cocktail. This is a
   set-cover and resistance-minimisation problem, barely addressed computationally.
3. **Population-level design.** Not "which phage for this patient" but "which fixed
   cocktail covers the most isolates circulating in Pakistani hospitals" — what a
   manufacturer or hospital pharmacy actually needs, and what your coverage map
   already positions you to answer.

Point 3 is the one you are uniquely placed to do, because you already have the
Pakistani capsule distribution and nobody else has published it.

---

## 3. Architecture

```
  bacterial isolate assembly (FASTA)
            |
     [1] receptor typing            Kaptive/Kleborate -> K locus, O locus
            |
     [2] defence profiling          DefenseFinder/PADLOC -> RM, CBASS, BREX
            |                       CRISPRCasFinder -> spacers
            |
     [3] phage candidate retrieval  INPHARED corpus, filtered to lytic (BACPHLIP)
            |
     [4] receptor match scoring     PhageHostLearn / RBP-to-K-locus evidence
            |
     [5] defence penalty            spacer hits, RM site density, known escapes
            |
     [6] cocktail assembly          set cover over non-overlapping receptors
            |
     [7] scored, evidence-graded report
```

Layers 1–3 assemble existing tools. Layer 4 is an existing model. **Layers 5 and 6
are the new science.** Layer 7 is what makes it usable.

---

## 4. Phased build

### Phase 1 — Reference phage corpus (2–3 weeks)

**Do:** download INPHARED, subset to *Klebsiella* phages, annotate each with
lifestyle (BACPHLIP), predicted RBPs and depolymerases, and any published host
range. Cross-link to the 34-record curated table you already have.

**Output:** `phage_reference.csv` — one row per phage with accession, genus,
lifestyle, RBP sequences, known capsule targets, evidence grade.

**Watch for:** most deposited phage genomes have **no** host-range data. Expect
only a few hundred *Klebsiella* phages with usable capsule annotation. That number
is the ceiling on everything downstream — measure it early and report it.

**Done when:** you can state, with a number, how many *Klebsiella* phages have a
capsule-typed host.

### Phase 2 — Reproduce PhageHostLearn (3–4 weeks)

**Do:** install it, run it on their published test set, confirm you reproduce the
reported performance, then run it on your 254 Pakistani genomes.

**Output:** a phage-by-isolate score matrix for the Pakistani cohort.

**Why before anything new:** if you cannot reproduce a published baseline you
cannot claim to beat it. It also tells you how many Pakistani isolates get *no*
confident phage match — your coverage gap re-derived by an independent method, and
a strong cross-check on the current paper.

**Risk:** may need more RAM than the laptop has. Run on Colab; that workflow is
already established.

### Phase 3 — Defence-system layer (4–6 weeks) — *first original contribution*

**Do:** run DefenseFinder and PADLOC across all 254 Pakistani genomes plus the 475
comparison genomes. Extract CRISPR spacers and search them against the phage
corpus. Build a per-isolate defence profile.

**Then answer:**

- How many defence systems does the average Pakistani clinical isolate carry?
- Do isolates of the uncovered capsule types (KL81, KL10, KL36) carry more or fewer?
- How often does a spacer in a Pakistani isolate match a phage that would otherwise
  be predicted to infect it?

That last question is publishable on its own and needs no new modelling — it is a
descriptive analysis of data you already hold.

**Output:** `defence_profile.csv`, and a rule that downgrades a receptor match when
a spacer hit or dense RM target site exists.

**Honest caveat:** the quantitative effect of any given defence system on phage
success is not established. A penalty term is a hypothesis, not a measurement, and
must be labelled as one.

### Phase 4 — Cocktail assembly (4–6 weeks) — *second original contribution*

**Do:** formulate as constrained set cover. Given the Pakistani capsule
distribution and the scored phage-by-capsule matrix, find the smallest phage set
that (a) covers the largest fraction of isolates and (b) covers every isolate with
at least two phages using **different receptors**, so one mutation cannot escape.

**Output:** a ranked national cocktail — "these 6 phages cover 71% of Pakistani
clinical *K. pneumoniae*, with dual-receptor redundancy for 58%" — plus the list of
capsule types no cocktail can currently reach.

**This is the headline result of the whole tool**, and it flows directly from the
coverage map already built.

**Watch for:** the answer is bounded by Phase 1's ceiling. If only 15 capsule types
have characterised phages, no cocktail exceeds the isolate share those types
represent. State that plainly rather than hiding it.

### Phase 5 — Validation (ongoing; decides credibility)

Retrospective validation is achievable without a lab:

1. **Held-out host-range matrices.** Find published phage-by-strain lysis tables
   where strains are capsule-typed. Predict, then compare. Report sensitivity,
   specificity and AUC — not accuracy; the matrix is heavily imbalanced.
2. **Leave-one-capsule-type-out.** Retrain excluding a capsule type entirely and
   test whether the model generalises to unseen types. This is the realistic
   clinical scenario and where most tools fail.
3. **Negative controls.** Confirm the model predicts *no* match for capsule types
   with no known phage. A model that finds a phage for everything is broken.

**Do not report cross-validated performance alone.** PhageHostLearn's contribution
was evaluating on the practical task and confirming in the lab; a tool evaluated
only in cross-validation will not be believed.

Wet-lab validation when it becomes possible: a single plaque assay of the
top-predicted phage against a KL81 Pakistani isolate would be worth more than any
further modelling. The group at The University of Haripur already isolates
*Klebsiella* phages from local sewage — the obvious collaboration.

### Phase 6 — Interface (2–3 weeks, only after Phase 5)

CLI first: assembly in, scored report out, one command. A web interface only once
predictions are trustworthy. Streamlit on a free tier suffices. Do not build a web
app around an unvalidated model.

---

## 5. Data you do not have and must obtain

| Need | Where | Difficulty |
|---|---|---|
| Phage genomes and host ranges | INPHARED, PhageScope, paper supplements | easy, tedious |
| Capsule-typed strains with lysis data | published supplementary tables | **the bottleneck** |
| Fresh Pakistani clinical isolates | hospital collaboration plus sequencing | hard; needs ethics approval |
| Local phage isolates | sewage sampling, wet lab | hard; needs a lab partner |

The bottleneck is not compute. It is **paired phage–host lysis data with typed
capsules**, and it is scarce for everyone. Curating a better set than currently
exists would itself be a contribution — you have already proved you can do that
kind of curation.

---

## 6. Where the Pakistan Genome Resource does and does not fit

PGR (Saleheen *et al.*, *Nature* 2026; 173,303 human exomes and genomes) is a
**human** resource. Which phage kills an infection is determined by the capsule
type of the infecting bacterium, not the patient's DNA, so PGR cannot drive layers
1–6 of this architecture. Two patients with identical genomes infected by KL64 and
KL81 strains need different phages.

Legitimate future use — a separate project, not this tool:

- **Host-response module.** With roughly 34,000 individuals carrying homozygous
  loss-of-function variants, PGR could be asked which immune, complement or
  phagocytosis genes are naturally knocked out in Pakistanis, and whether those
  variants plausibly affect phage clearance or therapy outcome.
- **Blocked by:** no established link between host genotype and phage-therapy
  outcome; data access and ethics approval; no Pakistani phage-therapy outcome
  cohort to test against.

Treat it as Phase 3 of a research programme, not a component of the tool.

---

## 7. Risks and kill criteria

Decide these now, in writing, so sunk cost does not decide them later.

| Risk | Kill or pivot criterion |
|---|---|
| Too few capsule-typed phages to model | If Phase 1 yields fewer than 100 usable phage–capsule pairs, drop the ML ambition and ship a curated database plus cocktail optimiser |
| Cannot reproduce PhageHostLearn | Stop and diagnose before building on it; publish the reproduction failure if it is real |
| Defence penalty has no measurable effect | Report the null result — publishable and useful |
| Hardware limits | Everything heavy runs on Colab; if a step cannot, cut the step |

---

## 8. What "finished" looks like

A researcher supplies an assembly. Within minutes they receive: the capsule type; a
ranked list of published phages predicted to lyse it, each with an evidence grade;
a warning flag for any defence system or CRISPR spacer arguing against those
predictions; and a suggested minimal cocktail with non-overlapping receptors. Every
claim traceable to a citation or to a stated model with a reported error rate.

If a capsule type has nothing, it says so — which, given that 47.6% of Pakistani
isolates fall into that category, will be a common and honest answer.

---

## 9. Suggested order

1. Finish and submit the current paper. It is the foundation and is nearly done.
2. Phase 1 (corpus) and the descriptive half of Phase 3 (defence systems across the
   cohorts you already have) — both self-contained and publishable.
3. Phase 2 (reproduce the baseline).
4. Phase 4 (cocktail design) — the headline.
5. Phase 5 validation throughout, never at the end.
6. Interface last.

Phases 1 and 3 need no new data and no new permissions. Start there.
