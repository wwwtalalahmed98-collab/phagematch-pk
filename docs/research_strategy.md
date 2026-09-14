# Research strategy: from a finished manuscript to a programme

Written 14 September 2026.

This answers four questions in order: where we actually are, what to do next and
why, whether the work matters, and what would genuinely add value versus what
would only add effort.

---

## 1. Where we actually are

The *Klebsiella* capsule coverage study has been finished since **21 August**.
Manuscript, three figures, five supplementary tables, 34 references, a public
GitHub repository and a Zenodo DOI. Nothing has changed in the repository since.

**Three weeks have passed and the paper has not been posted or submitted.**

That is the single most important fact in this document. The binding constraint
on this project is not ambition, data or compute. It is shipping. A finished
paper on a hard drive has exactly the same scientific value as no paper at all,
and it decays: capsule databases update, comparable studies appear, and the
"first description of phage coverage in Pakistani *K. pneumoniae*" claim is only
true until someone else makes it.

Everything below is sequenced around fixing that first.

---

## 2. Decision 1 — post the preprint this week

**Why now, before anything else.**

*It is nearly free.* The manuscript is complete and formatted. Posting to bioRxiv
costs perhaps two hours, no money, and screening takes about 48 hours.

*It converts finished work into a citable object immediately.* You get a DOI and
a permanent public record dated to you, rather than an unpublished file.

*It removes the risk of being scooped while you decide.* Small, but real: nobody
else has published Pakistani capsule coverage, and that is precisely the sort of
gap someone else can close in a few weeks.

*The Microbiology Society encourages it and accepts direct submission from
bioRxiv.* So preprinting does not delay journal submission; it shortens it. The
society actively supports preprint posting prior to submission, and journals in
its suite take submissions straight from bioRxiv.

*It is the highest-leverage thing two unknown students can do.* Your institution
is not one editors recognise, and neither of you has a publication record. A
preprint is visible regardless of what any editor decides, and it is the thing
you can put in an email when you approach a collaborator.

**What could go wrong, honestly.** A preprint is permanent — if the analysis has
an error, it stays visible with a version history. That argues for care, which
the clonality analysis already demonstrates, not for delay. There is no journal
here that would refuse the paper because it was preprinted.

**Do this week:** post to bioRxiv (subject area: Microbiology), then submit to
*Microbial Genomics* directly from bioRxiv.

---

## 3. Does this work matter?

An honest assessment, because the answer shapes what to build next.

**What it establishes.** That roughly half of deposited Pakistani clinical
*K. pneumoniae* isolates belong to capsule types with no published phage, and
that at least one such type — KL81 — is South Asian and absent from 275 genomes
from the regions where *Klebsiella* phages are actually isolated. Nobody has
shown this for South Asia before.

**Who it is useful to, concretely.**

- Anyone considering an imported phage cocktail for a South Asian hospital now
  has a documented reason to check the capsule match first.
- Phage hunters in the region get a named, justified target: KL81.
- Anyone doing comparative genomics on public bacterial genomes gets a worked
  demonstration that BioProject clustering can manufacture significance.

**The most transferable contribution is the methodological one.** Four of six
nominally significant geographic differences vanished when each BioProject was
counted once. That finding generalises far beyond *Klebsiella* and beyond
Pakistan, and it is the part of this paper most likely to be cited by people who
do not care about phages at all.

**What it does not establish, and must never be claimed.** It does not estimate
how common any capsule type is in Pakistan — two BioProjects supply 61% of the
cohort and all 13 KL81 isolates come from one. It does not show that any phage
works against any isolate. No wet-lab experiment was performed.

**So: does it matter?** Yes, but modestly and specifically. It is a well-executed,
honestly-bounded descriptive study that opens a question rather than closing one.
Its larger value is as a foundation: it gives you a citable output, a public
codebase, a defensible method, and a concrete reason for a wet-lab group to talk
to you. Treating it as the end of the work would waste it; treating it as the
start is correct.

---

## 4. What adds value, ranked

Ranked by value gained per unit of effort and risk.

### Tier 1 — do these

**A. Post the preprint and submit.** Two hours. Everything else depends on it.

**B. Approach the Haripur group.** The University of Haripur published a lytic
*Klebsiella* phage isolated from local sewage this year (PMID 41847192). They are
in your city and doing the wet work your discussion says is needed.

*Why it matters:* one plaque assay of any phage against a KL81 isolate would do
more for this project's credibility than another year of computation. A purely
computational paper is easy to dismiss; a computational paper with one confirming
experiment is not.

*What to send:* the preprint link, one paragraph on the KL81 gap, and a specific
small ask — not "let us collaborate" but "would you be willing to test whether
any of your isolates is KL81".

**C. Defence-system analysis of the genomes you already hold.** Run DefenseFinder
and PADLOC across the 254 Pakistani and 475 comparison genomes; extract CRISPR
spacers and match them against known *Klebsiella* phages.

*Why it matters:* it needs no new data, no permissions and no money. It adds a
biological dimension nobody has combined with capsule coverage, and it answers a
question that directly affects phage therapy — how often does a receptor-matched
phage still fail because the host is armed? It is a second paper sitting inside
data already on your disk.

### Tier 2 — do after Tier 1 lands

**D. Extend the analysis across South Asia.** Roughly 3,000 *K. pneumoniae*
genomes from India, Bangladesh and Nepal meet the same criteria, against your 254.

*Why it matters:* it fixes the weakness you already identified. KL15, KL48, KL51
and the KL64 contrast collapsed under BioProject correction because the cohort was
too small and too clustered. Thousands of genomes across hundreds of projects
would resolve them properly. It also upgrades the claim from "Pakistan" to "South
Asia", which is both better supported and more interesting.

*Cost:* the pipeline exists. This is mostly compute time and patience with Colab.

**E. Cocktail design over the coverage map.** Formulate as constrained set cover:
the smallest phage set covering the most isolates, with every isolate covered by
at least two phages using different receptors.

*Why it matters:* this is the question a hospital pharmacy or manufacturer
actually asks, and nobody has answered it for this region. It converts a
descriptive map into a design recommendation.

### Tier 3 — later, or never

**F. The full prediction tool.** See `tool_roadmap.md`. Worth building only after
C and E exist, and only as an interface over validated components.

**G. The Pakistan Genome Resource host-factor module.** Scientifically interesting,
but it is a different project with a different data-access problem and an
unvalidated premise. Do not let it displace Tier 1.

---

## 5. What does not add value

Naming these explicitly, because each is tempting.

**More polishing of the current manuscript.** It has been checked line by line.
Further passes are procrastination wearing the costume of rigour.

**More Pakistani genomes from the same BioProjects.** The cohort's problem is
clustering, not count. Adding 40 genomes changed nothing for KL36 and KL48, and
another 200 from the same two projects would change nothing either.

**Rebuilding PhageHostLearn.** Strain-level *Klebsiella* phage–host prediction is
solved and lab-validated (Boeckaerts *et al.*, *Nat Commun* 2024). Use it.

**Building the web interface early.** An interface over unvalidated predictions
creates the appearance of a product and the reality of a liability.

**Waiting for the journal decision before starting C.** Review takes months. The
defence-system analysis is independent of the outcome.

---

## 6. Twelve-month sequence

| When | What | Output |
|---|---|---|
| This week | Post preprint; submit to *Microbial Genomics* via bioRxiv | DOI, submission ID |
| Week 1–2 | Email the Haripur group with the preprint and one specific ask | A conversation, or a clear no |
| Month 1–2 | Defence-system profiling of existing cohorts (Tier 1C) | Analysis + draft of paper 2 |
| Month 2–4 | South Asia-wide extension (Tier 2D) | Resolves the collapsed types |
| Month 4–6 | Paper 2 submitted; cocktail design begun (Tier 2E) | Second submission |
| Month 6–12 | Cocktail paper; tool only if C and E succeeded | Third output, or an honest stop |

Two papers in twelve months from data already on disk is a realistic and strong
outcome for two undergraduates. Three would be unusual.

---

## 7. Decision rules

Write these down now so momentum, not sunk cost, decides later.

- **If the preprint is not posted within seven days**, the problem is not the
  science. Post an imperfect version; bioRxiv supports revisions.
- **If the Haripur group does not reply within three weeks**, send one follow-up,
  then proceed computationally and stop waiting.
- **If defence-system profiling shows no difference** between covered and
  uncovered capsule types, publish the null. It is a real result and it saves
  others the work.
- **If *Microbial Genomics* rejects**, do not rewrite from scratch. Send to
  *Journal of Global Antimicrobial Resistance* or *Microbiology Spectrum* within
  two weeks, with the reviewer comments addressed.

---

## 8. The one-sentence strategy

Ship what is finished this week, use it to open a wet-lab conversation, and spend
the review period turning the data already on your disk into the defence-system
paper — then scale to South Asia once the method has survived contact with
reviewers.
