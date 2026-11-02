"""The frontend's lint runs, and runs in CI.

Two settings switched it off between them. `craco.config.js` handed the
ESLint plugin a config that *replaced* CRA's rather than extending it, so the
build linted with `eslint-config-react-app/base` alone — a parser and two JSX
rules, no `no-undef` — and an undefined identifier compiled and threw at
runtime. And CI built with `CI: "false"`, so any warning that did fire was a
log line. Turning both back on found a `<Navigate>` that was never imported
(a creator with an untouched profile hit a ReferenceError on /dashboard) and a
`useCallback` reading a `const` declared two hundred lines below it in the
admin action queue.
"""

from pathlib import Path

import server

ROOT = Path(server.__file__).parent.parent


def test_craco_extends_the_full_react_app_config():
    src = (ROOT / "frontend" / "craco.config.js").read_text()
    assert 'require.resolve("eslint-config-react-app"' in src
    assert "extends: [reactAppEslintConfig]" in src
    # The shape that disabled it: a configure block naming only the hooks
    # plugin. CRA's react-app config already carries those rules.
    assert '"plugin:react-hooks/recommended"' not in src


def test_ci_treats_lint_warnings_as_failures():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert 'CI: "false"' not in ci
    assert 'CI: "true"' in ci
