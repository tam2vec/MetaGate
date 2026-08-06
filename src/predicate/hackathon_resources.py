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
        "description": "The local DataHub deployment used to run the live Predicate proof.",
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
        "description": "The open-source catalog platform that stores the graph Predicate evaluates.",
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
        "description": "A trip-record pipeline with a planted freshness problem.",
        "url": "https://github.com/datahub-project/static-assets/tree/main/datasets/nyc-taxi",
        "load_command": None,
        "status": "use the hackathon recipe, then discover its resulting URNs",
    },
    {
        "id": "healthcare",
        "name": "Healthcare",
        "kind": "scenario",
        "description": "Synthetic patient data with planted quality issues.",
        "url": "https://github.com/datahub-project/static-assets/tree/main/datasets/healthcare",
        "load_command": None,
        "status": "use the hackathon recipe, then discover its resulting URNs",
    },
    {
        "id": "fiction-retail",
        "name": "Fiction Retail",
        "kind": "scenario",
        "description": "A clean multi-table retail graph for testing definitions and lineage.",
        "url": "https://github.com/datahub-project/static-assets/tree/main/datasets/fiction-retail",
        "load_command": None,
        "status": "use the hackathon recipe, then discover its resulting URNs",
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
