FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY scripts ./scripts
COPY examples ./examples

RUN python -m pip install --no-cache-dir -e .
RUN python -c "from predicate.review import main; from context_gradient.datahub.adapter import DataHubEvidenceExtractor"

ENV PREDICATE_DEMO_MODE=fixture
ENV DATAHUB_GRAPHQL_URL=""
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=3).read()"

CMD ["sh", "-c", "if [ \"$PREDICATE_DEMO_MODE\" = \"live\" ]; then exec predicate-review --host 0.0.0.0 --port 8765 --policy examples/policies/enterprise_ai.yml --datahub-url \"$DATAHUB_GRAPHQL_URL\" --no-recorded-fallback; else exec predicate-review --host 0.0.0.0 --port 8765 --policy examples/policies/enterprise_ai.yml --datahub-file examples/data/datahub_graph.json; fi"]
