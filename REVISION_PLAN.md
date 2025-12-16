# Manuscript Revision Plan: Results & Analysis Restructuring

## Executive Summary

This plan restructures the Results section to follow a **hypothesis-driven narrative arc** that:
1. Establishes the empirical puzzle (porosity paradox)
2. Builds explanatory evidence systematically (Stage I → Stage II)
3. Adjudicates between competing hypotheses using Bayesian model comparison
4. Explicitly answers all three research questions with quantitative evidence
5. Separates objective findings (Results) from interpretation (Discussion)

---

## Current Problems

| Issue | Description |
|-------|-------------|
| **Repetition** | The same coefficient estimates appear in narrative text AND separate tables for each model |
| **Fragmented tables** | Four separate model tables (volumetric, hydraulic, combined, GDI) when one consolidated table would be clearer |
| **Missing RQ answers** | Research questions are posed but never explicitly answered with evidence |
| **Missing posterior rankings** | Methodology promises Pr(j ∈ Top-K | data) but Results never shows them |
| **No Discussion section** | Design interpretation is mixed into Results; no limitations or synthesis |
| **No Conclusion** | Paper ends abruptly after Results |
| **Narrative weakness** | Sections read as technical reports rather than building a scientific argument |

---

## Proposed Structure

### RESULTS (Section 3) — *What We Found*

The Results section should present findings **objectively** without interpretation, following a logical evidence-building sequence.

#### 3.1 The Porosity Paradox: Empirical Evidence Against the Volumetric Assumption

**Purpose**: Establish the puzzle that motivates the Bayesian analysis.

**Narrative Arc**:
- Open with the conventional expectation (higher porosity → better retention)
- Present Table 1 (packing summary) showing the five media
- Highlight the critical counter-example: glass marbles (ε=0.40, R=0.13) vs pea gravels (ε=0.36, R=0.86)
- Compute void-normalized retention to show it's not a "space" effect
- Present Figure 1 (retention vs porosity scatter)
- **Closing hook**: This paradox cannot be explained by porosity alone—what explains it?

**Table**: Tab 1 — Packing Media Properties and Retention Outcomes (existing tab_packing_summary)

**Figure**: Fig 1 — Retention vs Porosity (existing fig_retention_vs_porosity)

**Key Evidence**:
- 6.7× difference in retained mass (19.1g vs 126.9g) despite similar porosity
- 7× difference in void-normalized retention (0.17 vs 1.21 g/mL)

---

#### 3.2 Stage I Results: Hydraulic Signatures Reveal Medium-Specific Flow Resistance

**Purpose**: Show that packing media have distinct hydraulic "fingerprints" extractable from pressure-drop data.

**Narrative Arc**:
- Introduce the Stage I Bayesian Darcy-Forchheimer calibration
- Present posterior estimates for permeability (k) and Forchheimer coefficient (β)
- Highlight the 115× range in k across media
- Note pea gravels' exceptionally high β (3.37×10⁵) indicating strong form drag
- Show posterior predictive fits match observations well
- Acknowledge GDI limitation (collapsed to ~0) and explain why

**Table**: Tab 2 — Hydraulic Signature Parameters (existing tab_hydraulic_signature)

**Figure**: Fig 2 — Pressure-Drop Calibration Fits (existing fig_pressure_drop panels, consider 2×3 grid)

**Key Evidence**:
- k ranges from 1.53×10⁻⁸ (pea gravels) to 1.76×10⁻⁶ (medium pumice) m²
- β for pea gravels is 100× higher than glass marbles
- Tight credible intervals for k; wider for β (expected in laminar regime)

---

#### 3.3 Stage II Results: Competing Retention Models

**Purpose**: Present the four competing Beta regression models and their coefficient estimates.

**Narrative Arc**:
- Explain the four hypotheses being tested:
  1. Volumetric (porosity-only)
  2. Hydraulic (k and β only)
  3. Combined (porosity + hydraulic signatures)
  4. GDI (geometry-derived index)
- Present **ONE consolidated table** with all model coefficients side-by-side
- Report posterior sign probabilities as key evidence
- Note that GDI model shows null effect (confirms Stage I limitation)

**Table**: Tab 3 — **NEW CONSOLIDATED TABLE**: Stage II Regression Coefficients Across Competing Models

| Parameter | Volumetric | Hydraulic | Combined | GDI |
|-----------|------------|-----------|----------|-----|
| Intercept (α) | est [HDI] | est [HDI] | est [HDI] | est [HDI] |
| β_logit(ε) | est [HDI], P(>0)=X | — | est [HDI], P(>0)=X | — |
| β_log(k) | — | est [HDI], P(>0)=X | est [HDI], P(>0)=X | — |
| β_log(1+β_F) | — | est [HDI], P(>0)=X | est [HDI], P(>0)=X | — |
| β_log(GDI) | — | — | — | est [HDI], P(>0)=X |
| κ (dispersion) | est | est | est | est |

**Figure**: Fig 3 — Forest Plot of Regression Coefficients (existing fig_forest panels as 2×2 grid)

**Key Evidence**:
- Combined model: P(β_log(1+β_F) > 0) = 0.95 (strongest effect)
- Combined model: P(β_logit(ε) > 0) = 0.88, P(β_log(k) > 0) = 0.88
- GDI: P(β_log(GDI) > 0) ≈ 0.50 (null)
- κ increases from volumetric (2.82) → hydraulic (3.37) → combined (4.44)

---

#### 3.4 Bayesian Model Comparison: Predictive Evidence

**Purpose**: Adjudicate between models using principled out-of-sample prediction.

**Narrative Arc**:
- Present PSIS-LOO cross-validation results
- Rank models by ELPD and pseudo-BMA weights
- Show where models succeed and fail via posterior predictive retention
- Highlight glass marbles as the critical discriminating case

**Table**: Tab 4 — Model Comparison (existing tab_model_comparison)

**Table**: Tab 5 — Posterior Predictive Retention by Medium (existing tab_retention_predictions, but ADD observed values for direct comparison)

**Figure**: Fig 4 — Retention vs Permeability (existing fig_retention_vs_k)

**Key Evidence**:
- Combined model: ELPD = -0.995, weight = 0.40 (best)
- Volumetric model over-predicts glass marbles: predicted μ=0.537 vs observed R=0.130
- Combined model correctly separates smooth (low R) from frictional (high R) media

---

#### 3.5 Posterior Ranking Probabilities for Design Decisions

**Purpose**: Answer RQ3 explicitly with quantitative posterior rankings.

**Narrative Arc**:
- Define the ranking probability: Pr(medium j is Top-K performer | data)
- Present a NEW table showing these probabilities for K=1, K=2, K=3
- Identify the probabilistic "winners" and "losers"
- Note that rankings propagate uncertainty from both stages

**Table**: Tab 6 — **NEW TABLE**: Posterior Ranking Probabilities Under Combined Model

| Medium | Pr(Rank=1) | Pr(Top-2) | Pr(Top-3) | Pr(Bottom-2) |
|--------|------------|-----------|-----------|--------------|
| Medium pumice | X% | X% | X% | X% |
| Pea gravels | X% | X% | X% | X% |
| Small pumice | X% | X% | X% | X% |
| White pebbles | X% | X% | X% | X% |
| Glass marbles | X% | X% | X% | X% |

**Key Evidence**:
- Medium pumice and pea gravels dominate top rankings
- Glass marbles has highest Pr(Bottom-2)
- Rankings respect uncertainty (no medium has Pr(Rank=1) = 100%)

---

### DISCUSSION (Section 4) — *What It Means*

The Discussion section **interprets** findings, answers research questions explicitly, and acknowledges limitations.

#### 4.1 Synthesis: Answering the Research Questions

**Purpose**: Explicitly answer each RQ with direct reference to evidence.

**Structure**:

**RQ1**: *Why does higher porosity correlate with lower retention in smooth media?*
- Answer: Because retention is **friction-limited**, not volume-limited
- Evidence: Glass marbles have moderate porosity but lowest β (low form drag) → lowest retention
- Evidence: Pea gravels have lower porosity but highest β (high form drag) → highest retention
- The volumetric model fails precisely for smooth media (Table 5: predicted 0.537 vs observed 0.130)

**RQ2**: *Do hydraulic signatures provide stronger evidence than porosity alone?*
- Answer: **Combined model provides strongest evidence**; neither alone is sufficient
- Evidence: PSIS-LOO weights — Combined (0.40) > Volumetric (0.23) > Hydraulic (0.18)
- Evidence: Posterior sign probability for β_log(1+β_F) = 0.95 in combined model
- Interpretation: Porosity contributes information about void structure; β contributes information about frictional dissipation; both matter

**RQ3**: *Can probabilistic rankings be derived for design decisions?*
- Answer: **Yes**, and they provide decision-relevant uncertainty quantification
- Evidence: Table 6 shows ranking probabilities
- Interpretation: Medium pumice and pea gravels are probabilistically preferred; glass marbles is probabilistically disfavored

---

#### 4.2 The Friction-Limited Retention Mechanism

**Purpose**: Provide mechanistic interpretation of the statistical findings.

**Narrative**:
- The Forchheimer coefficient β captures form drag arising from flow separation around irregular particle surfaces
- High β → energy dissipation → reduced hydrodynamic lift forces on retained biomass
- Glass marbles (spherical, smooth) minimize form drag → biomass easily displaced
- Pea gravels (irregular, rough) maximize form drag → biomass mechanically anchored
- This explains why permeability k alone is insufficient: medium pumice has highest k but also has surface roughness

---

#### 4.3 Implications for Underdrain System Design

**Purpose**: Translate findings into engineering recommendations.

**Recommendations**:
1. **Prioritize frictional damping over porosity** when selecting packing media
2. **Avoid smooth spherical media** (e.g., glass beads) despite favorable hydraulic conductivity
3. **Use posterior ranking probabilities** rather than deterministic indices for material selection
4. **Characterize candidate media via pressure-drop testing** to extract (k, β) signatures before deployment

---

#### 4.4 Limitations and Future Directions

**Purpose**: Acknowledge constraints and propose next steps.

**Limitations**:
1. **Small sample size (n=5)**: Credible intervals are wide; model selection is not decisive
2. **GDI collapse**: The geometry-derived index failed to discriminate media due to Ψ mapping issues
3. **Single reactor configuration**: Results may not generalize to different D, H, or flow regimes
4. **Endpoint measurement**: Time-resolved retention dynamics were not modeled

**Future Directions**:
1. **Image-based sphericity measurement**: Avoid inferring Ψ from pressure-drop correlations
2. **Expanded media library**: Test more packing types to improve model discrimination
3. **Temporal modeling**: Track retention dynamics, not just endpoints
4. **Independent validation**: Test predictions on held-out media configurations

---

### CONCLUSION (Section 5)

**Purpose**: Concise synthesis of contributions.

**Structure** (3-4 paragraphs):

1. **The problem and approach**: Tested whether porosity explains biomass retention using Bayesian model comparison with hydraulic signatures.

2. **Key finding**: Retention is friction-limited, not volume-limited. The combined model incorporating both porosity and hydraulic signatures (k, β) achieved the best predictive performance (ELPD = -0.995, weight = 0.40).

3. **Mechanistic insight**: The Forchheimer inertial coefficient β, which captures form drag from surface roughness, is the strongest predictor of retention (P(β > 0) = 0.95). This explains why smooth glass marbles fail despite moderate porosity.

4. **Practical implication**: Underdrain design should prioritize frictional damping characteristics, with material selection guided by posterior ranking probabilities rather than porosity-based heuristics.

---

## Implementation Checklist

| Task | Priority | Notes |
|------|----------|-------|
| Create consolidated Stage II coefficients table (Tab 3) | High | Replace 4 separate tables |
| Compute and add posterior ranking probability table (Tab 6) | High | New analysis required |
| Write Section 4.1 (RQ answers) | High | Core contribution |
| Write Section 4.2 (mechanism) | Medium | Interpretation |
| Write Section 4.3 (design implications) | Medium | Practical value |
| Write Section 4.4 (limitations) | Medium | Scientific rigor |
| Write Section 5 (conclusion) | High | Required for completeness |
| Reorganize existing Results content | High | Remove repetition |
| Update figure layouts (2×2 or 2×3 grids) | Low | Visual improvement |
| Add observed values to Tab 5 | Medium | Easier comparison |

---

## Narrative Flow Summary

```
Section 3.1: Here's a puzzle — porosity doesn't explain retention
     ↓
Section 3.2: But media have distinct hydraulic signatures (k, β)
     ↓
Section 3.3: We tested four hypotheses; combined model has strongest effects
     ↓
Section 3.4: Combined model also predicts best (PSIS-LOO evidence)
     ↓
Section 3.5: Here are the posterior rankings for design decisions
     ↓
Section 4.1: Explicitly answering: RQ1 (friction-limited), RQ2 (combined best), RQ3 (rankings work)
     ↓
Section 4.2: Mechanistic interpretation — form drag matters
     ↓
Section 4.3: What this means for engineers
     ↓
Section 4.4: What we can't claim; what's next
     ↓
Section 5: Summary of contributions
```

---

## Approval Requested

Please review this plan. Once approved, I will:
1. Restructure the Results section following the above outline
2. Create the consolidated coefficient table
3. Compute posterior ranking probabilities (requires checking if pipeline outputs this, or adding computation)
4. Write the Discussion and Conclusion sections
5. Remove redundant content and tables
