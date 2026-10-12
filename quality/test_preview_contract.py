from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PreviewContractTests(unittest.TestCase):
    def test_preview_cannot_promote_to_stable(self):
        preview = (ROOT / '.github/workflows/preview.yml').read_text(encoding='utf-8')
        stable = (ROOT / '.github/workflows/release.yml').read_text(encoding='utf-8')
        self.assertIn('workflow_dispatch:', preview)
        self.assertIn('tag="preview-${version}.${PREVIEW_SEQUENCE}"', preview)
        self.assertIn('--prerelease --latest=false', preview)
        self.assertIn('release-evidence', stable)
        self.assertIn('needs: verify', preview)
        for platform in ['Linux', 'Windows', 'macOS']:
            self.assertIn(f'preview-{platform}/core.zip', preview)
            self.assertIn(f'preview-{platform}/codex.zip', preview)
        self.assertIn('--git-ref HEAD', preview)
        self.assertIn('E2 pending', preview)

    def test_demo_is_labeled_and_does_not_track(self):
        html = (ROOT / 'docs/demo.html').read_text(encoding='utf-8')
        self.assertIn('<noscript>', html)
        self.assertIn('不是实时 AI', html)
        self.assertIn('role="status"', html)
        self.assertIn('demo-engine.js', html)
        for filename in ['demo.js', 'demo-engine.js']:
            js = (ROOT / 'docs/assets' / filename).read_text(encoding='utf-8')
            for forbidden in ['fetch(', 'XMLHttpRequest', 'localStorage', 'sendBeacon', 'innerHTML']:
                self.assertNotIn(forbidden, js)
