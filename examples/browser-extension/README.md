# MetaGate Browser Extension

This prototype makes MetaGate automatic on a local DataHub asset page.

When a user opens a DataHub dataset URL, the content script:

1. Reads the dataset URN from the browser URL.
2. Calls the local MetaGate review API.
3. MetaGate queries DataHub GraphQL through `metagate-review`.
4. The extension injects an allow/block panel into the DataHub page.
5. The panel shows readiness, confidence, reason, and a repair queue.

This is a packaged browser integration for the hackathon demo. It is
installable as a Chrome extension and automatically evaluates the DataHub asset
currently open in the browser. It is not a native DataHub frontend bundle:
native packaging depends on the target DataHub deployment's extension
mechanism.

## Package and Install

From the repository root, create a shareable extension bundle:

```bash
./scripts/package_extension.sh
```

The script creates `dist/MetaGate-DataHub-extension.zip`. Unzip it before
using **Load unpacked**; Chrome does not load a zip file through that button.
For development, Chrome can load the folder directly. For a different local
or private MetaGate API, open the extension's **Details** page, choose
**Extension options**, and save the API URL there. The URL is stored in Chrome
storage; no DataHub token is placed in the browser.

## Run It Locally

Start DataHub and make sure the GraphQL endpoint is available:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
```

Start the MetaGate API/review server:

```bash
metagate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml
```

The server should print:

```text
MetaGate Review is running at http://127.0.0.1:8765/review
```

### Start MetaGate automatically on macOS

Install the local background service once from the repository root:

```bash
./scripts/install_metagate_autostart.sh
```

This keeps the review API available at `http://127.0.0.1:8765` and restarts it
if it stops. The DataHub Docker deployment still needs to be running for live
metadata; the service does not start Docker or store DataHub credentials.

To stop automatic startup:

```bash
launchctl bootout "gui/$(id -u)/com.metagate.review"
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

The MetaGate panel should appear automatically on the right side of the page.

After changing extension files, return to `chrome://extensions`, click the
extension's **Reload** button once, then refresh the DataHub tab. This is a
Chrome requirement for unpacked extensions, not a MetaGate evaluation step.

## Screenshot Checklist

Capture one screenshot with:

- the DataHub URL bar showing the dataset URN
- the normal DataHub asset page still visible
- the MetaGate panel injected on the right
- the decision, readiness, confidence, and repair queue visible
- no private token, cookie, or customer data visible

Use this screenshot as the proof for:

> MetaGate can automatically evaluate the DataHub asset a user is already
> viewing. The packaged browser integration proves the automatic UX; native
> DataHub frontend registration remains deployment-specific.

## Demo Wording

Use:

> This browser extension prototype proves the automatic path: opening a DataHub
> asset page triggers MetaGate against that asset URN and renders the decision
> without a separate terminal command.

Avoid claiming that this browser extension is already installed inside every
DataHub deployment.
