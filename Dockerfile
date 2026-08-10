FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY scripts ./scripts
COPY examples ./examples
COPY public-demo ./public-demo

RUN python -m pip install --no-cache-dir -e ".[datahub]"
RUN python -c "from metagate.review import main; from context_gradient.datahub.adapter import DataHubEvidenceExtractor"

ENV METAGATE_DEMO_MODE=fixture
ENV DATAHUB_GRAPHQL_URL=""
ENV METAGATE_CATALOG_FIRST=0
ENV METAGATE_MAX_ASSETS=0
ENV METAGATE_BUILD_ID=metagate-catalog-first-v1
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8765'), timeout=3).read()"

CMD ["sh", "-c", "PORT=\"${PORT:-8765}\"; if [ \"$METAGATE_DEMO_MODE\" = \"live\" ]; then exec metagate-review --host 0.0.0.0 --port \"$PORT\" --policy examples/policies/enterprise_ai.yml --datahub-url \"$DATAHUB_GRAPHQL_URL\" --no-recorded-fallback --discover-assets --catalog-first --max-assets \"${METAGATE_MAX_ASSETS:-0}\"; else exec metagate-review --host 0.0.0.0 --port \"$PORT\" --policy examples/policies/enterprise_ai.yml --datahub-file examples/data/six_asset_review_graph.json --no-recorded-fallback; fi"]
