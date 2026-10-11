
import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from src.llm_engine import analyze_risk_with_llm

from src.evidence_fusion import fuse_evidence
from src.finbert_engine import analyze_finbert
from src.ingestion import fetch_news
from src.nlp_engine import analyze_text
from src.pipeline import RiskCascadeEngine


ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="RiskCascade",
    page_icon="📊",
    layout="wide",
)

engine = RiskCascadeEngine()

st.title("RiskCascade — Evidence-to-Impact Credit Risk Engine")
st.caption(
    "Live public headlines → financial sentiment and event detection → "
    "exposure propagation → illustrative portfolio stress"
)

st.warning(
    "Prototype limitations: FinBERT estimates financial-text sentiment. "
    "Event detection uses keyword heuristics. PD shocks, exposure data, "
    "and propagation parameters are illustrative, not calibrated forecasts."
)

live_tab, demo_tab = st.tabs(["Live News", "Synthetic Demo"])


def render_risk_result(results):
    """Render expected-loss metrics, exposure calculations, and graph."""

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Baseline expected loss",
        f"₹{results['baseline_el']:,.2f}",
    )
    c2.metric(
        "Stressed expected loss",
        f"₹{results['stressed_el']:,.2f}",
    )
    c3.metric(
        "Incremental expected loss",
        f"₹{results['delta_el']:,.2f}",
    )

    st.markdown("**Exposure-level calculations**")
    st.dataframe(results["exposures"], use_container_width=True)

    nodes = list(engine.G.nodes())
    node_index = {node: i for i, node in enumerate(nodes)}

    labels = [
        (
            f"{node}<br>"
            f"Shock: {results['stresses'].get(node, 0.0) * 100:.3f}%"
        )
        for node in nodes
    ]

    edge_sources = []
    edge_targets = []
    edge_values = []

   
    for u, v in engine.G.edges():
        transmitted = (
            results["stresses"].get(u, 0.0)
            * engine.G[u][v]["weight"]
            * engine.attenuation
        )

        # Hide edges that carry no meaningful shock.
        if transmitted <= 1e-10:
            continue

        edge_sources.append(node_index[u])
        edge_targets.append(node_index[v])
        edge_values.append(transmitted * 100)


    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    label=labels,
                    pad=18,
                    thickness=20,
                ),
                link=dict(
                    source=edge_sources,
                    target=edge_targets,
                    value=edge_values,
                ),
            )
        ]
    )

    fig.update_layout(
        title="Illustrative risk transmission through the exposure graph",
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_finbert_result(result):
    """Display local FinBERT output without conflating it with event detection."""

    st.markdown("### FinBERT financial sentiment")

    score = result["sentiment"]
    label = result["label"].title()

    c1, c2 = st.columns(2)
    c1.metric("Predicted sentiment", label)
    c2.metric("Sentiment score", f"{score:+.3f}")

    st.caption(
        "Score = positive probability − negative probability. "
        "Range: −1 to +1. This is a model score, not a probability of default."
    )

    scores = result["scores"]

    st.write("**Class probabilities**")
    st.bar_chart(
        {
            "Model score": {
                "Positive": scores["positive"],
                "Neutral": scores["neutral"],
                "Negative": scores["negative"],
            }
        }
    )

    st.caption(
        f"Model: {result['model']} | Inference: {result['method']} (local)"
    )


# ---------------------------------------------------------------------
# LIVE NEWS
# ---------------------------------------------------------------------

with live_tab:
    st.subheader("Live public news")

    if st.button("Fetch latest headlines", type="primary"):
        with st.spinner("Fetching public RSS feeds..."):
            st.session_state["live_news_result"] = fetch_news(
                max_per_feed=5,
                fetch_full_text=True,
            )

    feed_result = st.session_state.get("live_news_result")

    if feed_result is None:
        st.info(
            "Click **Fetch latest headlines** to retrieve current public "
            "RSS feed entries."
        )

    else:
        articles = feed_result["articles"]

        for error in feed_result["errors"]:
            st.error(error)

        st.write(f"Retrieved {len(articles)} unique headline entries.")

        if not articles:
            st.warning(
                "No headlines were retrieved. Check feed access and try again."
            )

        else:
            labels = [
                f"{article['title']} — {article['source']}"
                for article in articles
            ]

            selected_index = st.selectbox(
                "Choose an article to analyze",
                range(len(articles)),
                format_func=lambda i: labels[i],
                key="live_article_select",
            )

            article = articles[selected_index]
            article_id = article["article_id"]

            st.markdown(f"### {article['title']}")

            st.caption(
                f"Publisher: {article['source']} | "
                f"Published: {article['published_at'] or 'Not provided'}"
            )


            st.markdown("**Retrieved source evidence**")

            quality = article.get("evidence_quality", "unknown")
            status = article.get("content_status", "unknown")

            st.write(
                f"**Evidence quality:** {quality.replace('_', ' ').title()}"
            )
            st.write(
                f"**Retrieval status:** {status.replace('_', ' ').title()}"
            )

            if article.get("extraction_error"):
                st.caption(f"Retrieval note: {article['extraction_error']}")

            with st.expander("View retrieved text", expanded=True):
                st.write(article["text"])

            if quality == "full_text":
                st.success("Substantive document text was extracted.")
            elif quality == "summary_only":
                st.warning("Only summary text is available. Interpret results cautiously.")
            else:
                st.info("Only headline-level information is available.")

            if quality != "full_text":
                st.warning(
                    "AI outputs may be incomplete because the source text is incomplete. "
                    "Verify the original source before making risk decisions."
                )

            st.link_button("Open original source", article["url"])


            # ---------------------------------------------------------
            # REAL LOCAL FINBERT SENTIMENT
            # ---------------------------------------------------------

            st.divider()
            st.subheader("Financial sentiment analysis")

            if st.button(
                "Run FinBERT sentiment",
                type="primary",
                key="run_finbert",
            ):
                try:
                    with st.spinner(
                        "Running local FinBERT inference..."
                    ):
                        result = analyze_finbert(article["text"])

                    st.session_state["finbert_result"] = {
                        "article_id": article_id,
                        "result": result,
                    }

                except Exception as exc:
                    st.error(
                        f"FinBERT inference failed: {type(exc).__name__}: {exc}"
                    )

            finbert_data = st.session_state.get("finbert_result")

            if (
                finbert_data
                and finbert_data["article_id"] == article_id
            ):
                render_finbert_result(finbert_data["result"])



            # ---------------------------------------------------------
            # LOCAL LLM: EVIDENCE-GROUNDED RISK EXTRACTION
            # ---------------------------------------------------------

            st.divider()
            st.subheader("Local AI Risk Analyst")

            st.caption(
                "Powered by Qwen3 running locally through Ollama. "
                "The selected article text is processed on this machine."
            )

            if st.button(
                "Extract risk event with local LLM",
                key="run_local_llm",
            ):
                try:
                    with st.spinner(
                        "Extracting company, event and supporting evidence..."
                    ):
                        llm_result = analyze_risk_with_llm(article["text"])

                    st.session_state["last_llm_analysis"] = {
                        "article_id": article_id,
                        "result": llm_result,
                    }

                except Exception as exc:
                    st.error(
                        f"Local LLM analysis failed: "
                        f"{type(exc).__name__}: {exc}"
                    )

            llm_data = st.session_state.get("last_llm_analysis")

            if llm_data and llm_data["article_id"] == article_id:
                result = llm_data["result"]

                st.markdown("**Extracted risk signal**")

                c1, c2 = st.columns(2)
                c1.metric(
                    "Extracted company",
                    result["company"] or "Unknown",
                )
                c2.metric(
                    "Risk event type",
                    result["event_type"],
                )

                st.write("**Risk event**")
                st.write(result["risk_event"])

                st.write("**Supporting evidence**")

                if result["evidence"]:
                    st.success(result["evidence"])
                    evidence_verified = result["evidence"] in article["text"]
                    st.caption(
                        "Exact text match verified."
                        if evidence_verified
                        else "Evidence could not be verified."
                    )
                else:
                    st.warning(
                        "No exact supporting quote was found. "
                        "Do not use this result for automated risk calculations."
                    )

                st.caption(
                    f"Model: {result['model']} | "
                    f"Method: {result['method']} | "
                    f"Self-reported confidence: {result['confidence']:.2f} "
                    "(not calibrated)"
                )

                # Match the extracted company against known graph entities.
                extracted_company = result["company"]
                matched_entity = None

                if extracted_company:
                    for node, attrs in engine.G.nodes(data=True):
                        if attrs.get("type") == "Bank Exposure":
                            continue

                        if node.casefold() == extracted_company.casefold():
                            matched_entity = node
                            break

                if matched_entity:
                    st.success(
                        f"Exact exposure-graph match: {matched_entity}"
                    )
                elif extracted_company:
                    st.warning(
                        "The extracted company does not exactly match a "
                        "company in the current exposure graph. "
                        "No automatic portfolio stress was run."
                    )
                else:
                    st.info(
                        "The article does not provide a verified company name. "
                        "Company matching and portfolio stress are unavailable "
                        "for this LLM result."
                    )



            # ---------------------------------------------------------
            # KEYWORD EVENT DETECTION
            # ---------------------------------------------------------

            st.divider()
            st.subheader("Risk event detection")

            if st.button(
                "Analyze event and entity",
                key="analyze_live_event",
            ):
                known_entities = [
                    node
                    for node, attrs in engine.G.nodes(data=True)
                    if attrs.get("type") != "Bank Exposure"
                ]

                analysis = analyze_text(
                    article["text"],
                    known_entities=known_entities,
                )

                st.session_state["last_live_analysis"] = {
                    "article_id": article_id,
                    "analysis": analysis,
                }

            last_analysis = st.session_state.get("last_live_analysis")

            if (
                last_analysis
                and last_analysis["article_id"] == article_id
            ):
                analysis = last_analysis["analysis"]

                st.caption(
                    "Event and entity detection method: "
                    "deterministic keyword baseline"
                )

                c1, c2, c3 = st.columns(3)

                c1.metric(
                    "Detected entity",
                    analysis["entity"] or "Not detected",
                )
                c2.metric(
                    "Event type",
                    analysis["event_type"],
                )
                c3.metric(
                    "Keyword sentiment",
                    f"{analysis['sentiment']:+.2f}",
                )

                st.metric(
                    "Heuristic impact score",
                    f"{analysis['impact']}/10",
                )

                st.write(
                    "**Matched evidence terms:**",
                    ", ".join(analysis["evidence"]) or "None",
                )



                # -----------------------------------------------------
                # EVIDENCE FUSION
                # -----------------------------------------------------
                st.divider()
                st.subheader("Evidence fusion")

                finbert_data = st.session_state.get("finbert_result")
                llm_data = st.session_state.get("last_llm_analysis")

                finbert_result = (
                    finbert_data["result"]
                    if finbert_data
                    and finbert_data.get("article_id") == article_id
                    else None
                )

                llm_result = (
                    llm_data["result"]
                    if llm_data
                    and llm_data.get("article_id") == article_id
                    else None
                )

                known_entities = [
                    node
                    for node, attrs in engine.G.nodes(data=True)
                    if attrs.get("type") != "Bank Exposure"
                ]

                fused = fuse_evidence(
                    article=article,
                    finbert_result=finbert_result,
                    llm_result=llm_result,
                    keyword_result=analysis,
                    known_entities=known_entities,
                    mapped_events=set(engine.factor_mapping),
                )

                st.write("**Decision:**", fused["decision"])
                st.write("**Fused event:**", fused["event_type"])
                st.write("**Company:**", fused["company"] or "Unknown")
                st.write(
                    "**Exposure-graph match:**",
                    fused["graph_entity"] or "None",
                )

                if fused["evidence_verified"]:
                    st.success(fused["evidence_quote"])
                else:
                    st.warning("No exact supporting quote was verified.")

                st.write("**Review reasons:**")
                for reason in fused["reasons"]:
                    st.write(f"- {reason}")

                st.caption(
                    "Review aid only. Human approval is required before "
                    "portfolio stress analysis."
                )



                # -----------------------------------------------------
                # ILLUSTRATIVE PORTFOLIO STRESS
                # -----------------------------------------------------


                # -----------------------------------------------------
                # ILLUSTRATIVE PORTFOLIO STRESS — HUMAN APPROVAL GATE
                # -----------------------------------------------------
                st.divider()
                st.subheader("Portfolio stress analysis")

                if fused["eligible_for_stress_review"]:
                    st.success(
                        "Evidence checks passed. Review the extracted signal "
                        "before running the illustrative stress calculation."
                    )

                    st.write("**Company:**", fused["graph_entity"])
                    st.write("**Event:**", fused["event_type"])
                    st.write("**Verified evidence:**", fused["evidence_quote"])

                    approved = st.checkbox(
                        "I reviewed the evidence and approve this illustrative stress run.",
                        key=f"approve_stress_{article_id}",
                    )

                    if st.button(
                        "Calculate illustrative portfolio stress",
                        key=f"stress_{article_id}",
                        disabled=not approved,
                    ):
                        stress_event = {
                            "entity": fused["graph_entity"],
                            "event_type": fused["event_type"],
                            "sentiment": (
                                fused["keyword_sentiment"]
                                if fused["keyword_sentiment"] is not None
                                else 0.0
                            ),
                            "impact": (
                                fused["impact_score"]
                                if fused["impact_score"] is not None
                                else 1
                            ),
                            "evidence": [fused["evidence_quote"]],
                        }

                        results = engine.process_event(stress_event)
                        render_risk_result(results)

                        st.caption(
                            "Illustrative scenario only. Shock assumptions and "
                            "expected-loss estimates are not calibrated forecasts."
                        )
                else:
                    st.warning(
                        "Portfolio stress was not run. Evidence fusion has not "
                        "cleared the review gate."
                    )
                    st.write("**Decision:**", fused["decision"])
                    st.write("**Reasons:**")
                    for reason in fused["reasons"]:
                        st.write(f"- {reason}")



# ---------------------------------------------------------------------
# SYNTHETIC DEMO
# ---------------------------------------------------------------------

with demo_tab:
    st.subheader("Synthetic scenarios")

    demo_path = ROOT / "data" / "cached_events.json"

    try:
        with open(demo_path, encoding="utf-8") as file:
            demo_events = json.load(file)

        if not demo_events:
            st.warning("No synthetic scenarios are available.")

        else:
            selected_demo = st.selectbox(
                "Choose synthetic scenario",
                demo_events,
                format_func=lambda event: (
                    f"{event['event_id']} — {event['event_type']}"
                ),
                key="selected_demo_scenario",
            )

            st.warning(
                "Synthetic data only — not verified news or real credit "
                "exposures. Results are illustrative, not forecasts."
            )

            st.write(selected_demo["event_text"])

            st.write(
                "**Scenario sources:**",
                selected_demo["source_1"],
                selected_demo["source_2"],
            )

            if st.button(
                "Run synthetic scenario",
                key="run_synthetic_scenario",
            ):
                try:
                    results = engine.process_event(selected_demo)
                    render_risk_result(results)
                except Exception as exc:
                    st.error(
                        f"Synthetic scenario failed: "
                        f"{type(exc).__name__}: {exc}"
                    )

    except FileNotFoundError:
        st.error(f"Synthetic scenario file not found: {demo_path}")

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        st.error(
            f"Could not load synthetic scenarios: "
            f"{type(exc).__name__}: {exc}"
        )
