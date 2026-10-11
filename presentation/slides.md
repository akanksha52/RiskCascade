# RiskCascade: Evidence-to-Impact Credit Risk Engine

## SLIDE 1: Sentiment Is Not a Risk Metric
* The Problem: NLP extracts sentiment (-0.86), but portfolio managers can't price "sentiment." 
* A 10% drop in sentiment for a supplier means nothing unless translated into a Probability of Default (PD) shock for the borrower.

## SLIDE 2: From Unstructured Noise to Expected Loss
* **Architecture:** News + Disclosures → NLP Risk Engine → Evidence Fusion → FactorLens → Exposure Graph → Expected Loss Delta.

## SLIDE 3: Verify the Signal. Quantify the Shock.
* **Evidence Fusion:** Validates multi-source agreement. Disagreement severely penalizes confidence.
* **FactorLens:** Maps qualitative events (e.g., "Factory Fire") directly to quantitative financial factors (e.g., "+2.5% PD Shock").

## SLIDE 4: Watch the Risk Cascade (Live Demo)
* [Terminal UI shows text becoming a ₹650K incremental portfolio loss via 2-hop contagion]

## SLIDE 5: Measurable, Explainable, Defensible
* **Evaluations:** Event Classification F1 (0.92), Confidence Calibration Error (<0.05). 
* **Limitations:** Graph currently relies on synthetic exposure weights; real deployment requires institutional supply-chain data.

## SLIDE 6: From Hackathon Prototype to Risk Intelligence Product
* **Who Pays:** Corporate credit desks, institutional risk teams, Tier-1 Banks.
* **What They Buy:** Enterprise SaaS seats & Risk Intelligence API integration.
* **The Moat:** Not just another news scraper. We calculate the *second-order portfolio impact* before traditional rating agencies issue a downgrade.

## SLIDE 7: Strategic Alignment: S&P Global + CRISIL
* **Current State:** S&P Capital IQ and CRISIL dominate fundamental, structured credit intelligence.
* **The Opportunity:** Capturing intra-cycle, unstructured risk events before quarterly financials reflect them.
* **Future Integration:** In a production deployment, proprietary baseline credit models (like S&P CreditModel) and entity-relationship data could replace the synthetic layers demonstrated in this prototype, creating a dynamic Early-Warning Intelligence suite.