# Predicate Browser Extension Prototype

This prototype makes Predicate automatic on a local DataHub asset page.

When a user opens a DataHub dataset URL, the content script:

1. Reads the dataset URN from the browser URL.
2. Calls the local Predicate review API.
3. Predicate queries DataHub GraphQL through `predicate-review`.
4. The extension injects an allow/block panel into the DataHub page.
5. The panel shows readiness, confidence, reason, and a repair queue.

This is not a packaged production DataHub plugin. It is a browser-extension
integration path for the hackathon demo.

## Package and Install

From the repository root, create a shareable extension bundle:

```bash
./scripts/package_extension.sh
```

For development, Chrome can load the folder directly. For a different local
or private Predicate API, open the extension's **Details** page, choose
**Extension options**, and save the API URL there. The URL is stored in Chrome
storage; no DataHub token is placed in the browser.

## Run It Locally

Start DataHub and make sure the GraphQL endpoint is available:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
```

Start the Predicate API/review server:

```bash
predicate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml
```

The server should print:

```text
Predicate Review is running at http://127.0.0.1:8765/review
```

### Start Predicate automatically on macOS

Install the local background service once from the repository root:

```bash
./scripts/install_predicate_autostart.sh
```

This keeps the review API available at `http://127.0.0.1:8765` and restarts it
if it stops. The DataHub Docker deployment still needs to be running for live
metadata; the service does not start Docker or store DataHub credentials.

To stop automatic startup:

```bash
launchctl bootout "gui/$(id -u)/com.predicate.review"
```

Load the extension in Chrome:

1. Open `chrome://extensions`.
2. Turn on **Developer mode**.
3. Click **Load unpacked**.
4. Select this folder:

```text
examples/browser-extension
```

Open a local DataHub asset page, for example:

```text
http://localhost:9002/dataset/urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)/Columns
```

The Predicate panel should appear automatically on the right side of the page.

After changing extension files, return to `chrome://extensions`, click the
extension's **Reload** button once, then refresh the DataHub tab. This is a
Chrome requirement for unpacked extensions, not a Predicate evaluation step.

## Screenshot Checklist

Capture one screenshot with:

- the DataHub URL bar showing the dataset URN
- the normal DataHub asset page still visible
- the Predicate panel injected on the right
- the decision, readiness, confidence, and repair queue visible
- no private token, cookie, or customer data visible

Use this screenshot as the proof for:

> Predicate can automatically evaluate the DataHub asset a user is already
> viewing. The production DataHub plugin is future packaging; the automatic UX
> is proven here through the browser extension prototype.

## Demo Wording

Use:

> This browser extension prototype proves the automatic path: opening a DataHub
> asset page triggers Predicate against that asset URN and renders the decision
> without a separate terminal command.

Avoid:

> This is a production DataHub plugin.
