"""The DataHub resources named in the hackathon materials.

These are resource profiles, not invented dataset URNs. A profile becomes
reviewable only after its metadata is loaded into the connected DataHub.
"""

HACKATHON_RESOURCES = [
    {
        "id": "datahub-docs",
        "name": "DataHub Docs",
        "kind": "documentation",
        "description": "The reference hub for DataHub setup, agents, and platform behavior.",
        "url": "https://docs.datahub.com/",
        "status": "documentation",
    },
    {
        "id": "datahub-quickstart",
        "name": "DataHub Quickstart",
        "kind": "platform",
        "description": "The local DataHub deployment used to run the live MetaGate proof.",
        "url": "https://docs.datahub.com/docs/quickstart",
        "status": "documentation",
    },
    {
        "id": "datahub-mcp-server",
        "name": "DataHub MCP Server",
        "kind": "integration",
        "description": "A governed way for agents to read DataHub context.",
        "url": "https://github.com/acryldata/mcp-server-datahub",
        "docs_url": "https://docs.datahub.com/docs/dev-guides/agent-context/mcp-server",
        "status": "documentation",
    },
    {
        "id": "agent-context-kit",
        "name": "Agent Context Kit",
        "kind": "integration",
        "description": "Structured DataHub context for metadata-aware agent workflows.",
        "url": "https://docs.datahub.com/docs/dev-guides/agent-context/agent-context",
        "status": "documentation",
    },
    {
        "id": "datahub-skills",
        "name": "DataHub Skills",
        "kind": "integration",
        "description": "Reusable catalog skills for metadata-aware agent workflows.",
        "url": "https://docs.datahub.com/docs/dev-guides/agent-context/skills",
        "repository_url": "https://github.com/datahub-project/datahub-skills",
        "status": "repository",
    },
    {
        "id": "analytics-agent",
        "name": "Analytics Agent",
        "kind": "integration",
        "description": "DataHub's analytics-agent path for metadata-aware analysis.",
        "url": "https://docs.datahub.com/docs/features/feature-guides/analytics-agent",
        "status": "documentation",
    },
    {
        "id": "datahub-core",
        "name": "DataHub Core",
        "kind": "repository",
        "description": "The open-source catalog platform that stores the graph MetaGate evaluates.",
        "url": "https://github.com/datahub-project/datahub",
        "status": "repository",
    },
    {
        "id": "datahub-skills-repository",
        "name": "DataHub Skills Repository",
        "kind": "repository",
        "description": "The open-source home for DataHub Skills contributions.",
        "url": "https://github.com/datahub-project/datahub-skills",
        "status": "repository",
    },
    {
        "id": "showcase-ecommerce",
        "name": "Showcase Ecommerce",
        "kind": "datapack",
        "description": "A rich cross-platform graph with lineage, governance, glossary terms, and domains.",
        "url": "https://docs.datahub.com/docs/quickstart",
        "load_command": "datahub datapack load showcase-ecommerce --force",
        "status": "loadable with the DataHub CLI",
    },
    {
        "id": "bootstrap",
        "name": "Bootstrap",
        "kind": "datapack",
        "description": "A small starter graph for a quick end-to-end smoke test.",
        "url": "https://docs.datahub.com/docs/quickstart",
        "load_command": "datahub datapack load bootstrap --force",
        "status": "loadable with the DataHub CLI",
    },
    {
        "id": "nyc-taxi",
        "name": "NYC Taxi",
        "kind": "scenario",
        "description": "NYC Yellow Taxi trip records with a linear pipeline and a planted freshness issue.",
        "url": "https://github.com/datahub-project/static-assets/tree/main/datasets/nyc-taxi",
        "load_command": None,
        "status": "load the published recipe, then discover its resulting URNs",
        "pipeline_shape": "raw -> staging -> mart (linear)",
        "database_files": ["nyc_taxi.db", "nyc_taxi_pipeline.db"],
        "size_estimate": "~85 MB each",
        "expected_evidence": ["freshness timestamps", "linear upstream/downstream lineage", "quality results"],
        "urn_aliases": ["nyc-taxi", "nyc_taxi", "nyctaxi"],
    },
    {
        "id": "healthcare",
        "name": "Healthcare",
        "kind": "scenario",
        "description": "Synthetic patient records with a forked pipeline and planted data-quality issues.",
        "url": "https://github.com/datahub-project/static-assets/tree/main/datasets/healthcare",
        "load_command": None,
        "status": "load the published recipe, then discover its resulting URNs",
        "pipeline_shape": "raw -> staging -> billing + demographics (fork)",
        "database_files": ["healthcare.db"],
        "size_estimate": "~2 MB",
        "expected_evidence": ["branch lineage", "quality assertions", "ownership and definitions for sensitive context"],
        "urn_aliases": ["healthcare"],
    },
    {
        "id": "fiction-retail",
        "name": "Fiction Retail",
        "kind": "scenario",
        "description": "Synthetic global retail data covering orders, fulfillment, and returns across ten flat tables.",
        "url": "https://github.com/datahub-project/static-assets/tree/main/datasets/fiction-retail",
        "load_command": None,
        "status": "load the published recipe, then discover its resulting URNs",
        "pipeline_shape": "10 flat tables (no views)",
        "database_files": ["fiction-retail.db"],
        "size_estimate": "~95 MB",
        "expected_evidence": ["schema coverage", "definitions and glossary terms", "table lineage where present"],
        "urn_aliases": ["fiction-retail", "fiction_retail", "fictionretail"],
    },
    {
        "id": "datahub-slack",
        "name": "DataHub Slack",
        "kind": "community",
        "description": "The hackathon help channel for implementation questions and feedback.",
        "url": "https://join.slack.com/t/datahubspace/shared_invite/zt-3rxzw3uww-7F2k5mDpjKXIGLskiQPwLQ",
        "status": "community",
    },
    {
        "id": "datahub-town-halls",
        "name": "DataHub Town Halls",
        "kind": "community",
        "description": "DataHub community sessions for learning and connecting with maintainers.",
        "url": "https://datahub.com/community/datahub-town-halls/",
        "status": "community",
    },
]


def resource_catalog() -> list[dict]:
    """Return a copy so an API caller cannot mutate the shared catalog."""
    return [dict(resource) for resource in HACKATHON_RESOURCES]


def annotate_scenario_resources(resources: list[dict], discovered_urns: list[str]) -> list[dict]:
    """Mark scenario profiles only when a matching asset is in the connected catalog.

    The hackathon repositories describe ingestion scenarios, not guaranteed URNs.
    Matching is deliberately best-effort and never creates an asset or a score.
    """
    normalized_urns = [str(urn) for urn in discovered_urns]
    annotated = []
    for resource in resources:
        item = dict(resource)
        if item.get("kind") == "scenario":
            aliases = item.get("urn_aliases", [item.get("id", "")])
            aliases = [alias.replace("-", "_").lower() for alias in aliases]
            matches = [
                urn for urn in normalized_urns
                if any(alias and alias in urn.replace("-", "_").lower() for alias in aliases)
            ]
            item["loaded_urns"] = matches
            item["loaded_asset_count"] = len(matches)
            item["reviewable"] = bool(matches)
            item["ingestion_status"] = "loaded" if matches else "not_loaded"
            item["match_method"] = "best-effort URN alias match"
        annotated.append(item)
    return annotated
