import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ExtensionPackagingTest(unittest.TestCase):
    def test_manifest_declares_settings_and_storage(self):
        manifest = json.loads((ROOT / "examples/browser-extension/manifest.json").read_text())
        self.assertIn("storage", manifest["permissions"])
        self.assertEqual(manifest["options_page"], "options.html")
        self.assertTrue((ROOT / "examples/browser-extension/options.js").exists())

    def test_package_script_creates_bundle(self):
        output = ROOT / "dist/Predicate-DataHub-extension.zip"
        try:
            subprocess.run([str(ROOT / "scripts/package_extension.sh")], cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertTrue(output.exists())
        finally:
            output.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
