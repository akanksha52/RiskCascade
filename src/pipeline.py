
import json
from pathlib import Path

import networkx as nx


class RiskCascadeEngine:
    """Deterministic, explainable credit-risk propagation engine."""

    def __init__(self, graph_path=None, attenuation=0.5):
        if not 0 <= attenuation <= 1:
            raise ValueError("Attenuation must be between 0 and 1.")

        self.attenuation = float(attenuation)

        self.factor_mapping = {
            "Supply Disruption": {
                "sector": "Semiconductor",
                "factor": "Supplier Risk",
                "pd_shock": 0.04,
            },
            "Cyberattack": {
                "sector": "Auto Parts",
                "factor": "Operational Risk",
                "pd_shock": 0.02,
            },
        }

        if graph_path is None:
            graph_path = (
                Path(__file__).resolve().parent.parent
                / "data"
                / "exposure_graph.json"
            )

        self.load_graph(graph_path)

    def load_graph(self, graph_path):
        with open(graph_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        graph = nx.DiGraph()

        for node in data["nodes"]:
            graph.add_node(node["id"], **node)

        for edge in data["edges"]:
            graph.add_edge(
                edge["source"],
                edge["target"],
                weight=float(edge["dependency_weight"]),
            )

        if not nx.is_directed_acyclic_graph(graph):
            raise ValueError("Exposure graph must be a directed acyclic graph.")

        for source, target, attrs in graph.edges(data=True):
            weight = attrs["weight"]
            if not 0 <= weight <= 1:
                raise ValueError(
                    f"Invalid dependency weight on {source} -> {target}"
                )

        self.G = graph

    def process_event(self, raw_event: dict):
        entity = raw_event["entity"]
        event_type = raw_event["event_type"]

        if entity not in self.G:
            raise ValueError(f"Event entity not found in exposure graph: {entity}")

        factor = self.factor_mapping.get(event_type)

        if factor is None:
            raise ValueError(f"No FactorLens mapping for event: {event_type}")

        impact = raw_event.get("impact")
        sentiment = raw_event.get("sentiment")
        confidence = raw_event.get("confidence")

        # Use transparent defaults when NLP has not estimated a value.
        impact = 5 if impact is None else float(impact)
        sentiment = 0.0 if sentiment is None else float(sentiment)
        confidence = 0.5 if confidence is None else float(confidence)

        if not 1 <= impact <= 10:
            raise ValueError("Impact must be between 1 and 10.")
        if not -1 <= sentiment <= 1:
            raise ValueError("Sentiment must be between -1 and 1.")
        if not 0 <= confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1.")

        severity_multiplier = impact / 10.0
        negative_multiplier = (1.0 + max(0.0, -sentiment)) / 2.0
        confidence_multiplier = 0.5 + 0.5 * confidence

        initial_shock = (
            factor["pd_shock"]
            * severity_multiplier
            * negative_multiplier
            * confidence_multiplier
        )

        result = self._propagate_shock(entity, initial_shock)
        result["shock_calculation"] = {
            "maximum_event_shock": factor["pd_shock"],
            "impact": impact,
            "sentiment": sentiment,
            "confidence": confidence,
            "severity_multiplier": severity_multiplier,
            "negative_multiplier": negative_multiplier,
            "confidence_multiplier": confidence_multiplier,
            "initial_shock": initial_shock,
            "method": "illustrative_heuristic_v1",
        }

        result["event"] = {
            "entity": entity,
            "event_type": event_type,
            "sentiment": raw_event.get("sentiment"),
            "impact": raw_event.get("impact"),
            "evidence": raw_event.get("evidence", []),
        }
        result["factor"] = factor.copy()

        return result

    def _propagate_shock(self, source_entity: str, initial_shock: float):
        if not 0 <= initial_shock <= 1:
            raise ValueError("Initial PD shock must be between 0 and 1.")

        # Calculate each node's shock in topological order.
        stresses = {source_entity: initial_shock}

        for node in nx.topological_sort(self.G):
            if node not in stresses:
                continue

            for downstream in self.G.successors(node):
                weight = self.G[node][downstream]["weight"]
                transmitted = (
                    stresses[node] * weight * self.attenuation
                )

                # Multiple upstream paths add their contributions.
                stresses[downstream] = (
                    stresses.get(downstream, 0.0) + transmitted
                )

        # Calculate losses at the borrower level, not using the loan node's PD.
        exposure_results = []
        baseline_el = 0.0
        stressed_el = 0.0

        for node, attrs in self.G.nodes(data=True):
            if attrs.get("type") != "Bank Exposure":
                continue

            predecessors = list(self.G.predecessors(node))
            if len(predecessors) != 1:
                raise ValueError(
                    f"Exposure {node} must have exactly one borrower predecessor."
                )

            borrower = predecessors[0]
            borrower_attrs = self.G.nodes[borrower]

            pd_base = float(borrower_attrs["baseline_pd"])
            lgd = float(attrs["lgd"])
            ead = float(attrs["ead"])

            if not 0 <= pd_base <= 1:
                raise ValueError(f"Invalid baseline PD for {borrower}.")
            if not 0 <= lgd <= 1:
                raise ValueError(f"Invalid LGD for {node}.")
            if ead < 0:
                raise ValueError(f"Negative EAD for {node}.")

            pd_shock = stresses.get(borrower, 0.0)
            pd_stressed = min(1.0, pd_base + pd_shock)

            el_before = pd_base * lgd * ead
            el_after = pd_stressed * lgd * ead

            baseline_el += el_before
            stressed_el += el_after

            exposure_results.append({
                "exposure": node,
                "borrower": borrower,
                "ead": ead,
                "baseline_pd": pd_base,
                "pd_shock": pd_stressed - pd_base,
                "stressed_pd": pd_stressed,
                "lgd": lgd,
                "baseline_el": el_before,
                "stressed_el": el_after,
                "delta_el": el_after - el_before,
            })

        return {
            "baseline_el": baseline_el,
            "stressed_el": stressed_el,
            "delta_el": stressed_el - baseline_el,
            "stresses": stresses,
            "exposures": exposure_results,
        }
