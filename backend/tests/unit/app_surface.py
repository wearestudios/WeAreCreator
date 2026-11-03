"""Which frontend files are the signed-in app's, walked from the router.

Not a test module: `test_app_type.py` and `test_site_foundations.py` import it.

The app is every route `isAppPath` says yes to — the dashboards, the console,
the manager screens, onboarding, authoring a brief. Its type is Manrope and
its rules are not the public site's, so the question several tests ask is
"which files only ever render inside the app?". The answer is read off
`App.js` rather than guessed from folder names:

* every component a route mounts is resolved through App.js's imports — the
  `load(() => import(...))` pages, the `adminRoute("...")` sections and the
  static imports;
* each route is an app route or not by the same rule `isAppPath` uses;
* everything those components import, transitively, is that side's;
* **App.js's own static imports are the shell**, rendered around every route
  including the public ones, so they count on the public side.

`APP_ONLY` is what is reachable from an app route and from nothing else. A
file in both (`SHARED`) renders on a public page too, which is why the app's
scope in `index.css` redirects the family tokens rather than trusting every
file to have been rewritten.
"""
from __future__ import annotations

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[3] / "frontend"
SRC = FRONTEND / "src"

# The same lists `lib/surfaceTheme.js` holds; `test_app_type.py` checks the
# two agree rather than trusting this copy.
PRODUCT_PREFIXES = ["/dashboard", "/onboarding", "/profile", "/admin", "/manager",
                    "/calendar", "/check-in", "/brand/"]
APP_EXCLUDED_PATHS = ["/admin/login"]


def is_app_path(path: str) -> bool:
    bare = path.rstrip("/") or "/"
    if bare in APP_EXCLUDED_PATHS:
        return False
    if path == "/campaigns/new" or re.match(r"^/campaigns/[^/]+/edit/?$", path):
        return True
    return any(path == p.rstrip("/") or path.startswith(p) for p in PRODUCT_PREFIXES)


def code_of(text: str) -> str:
    """Source with block comments, JSX comments and whole `//` lines removed."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))


def _resolve(base: Path):
    for cand in (base, base.with_suffix(".jsx"), base.with_suffix(".js"),
                 base / "index.js", base / "index.jsx"):
        if cand.is_file():
            return cand
    return None


def imports(path: Path):
    """Files under `src/` this one imports, statically or lazily."""
    text = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
    text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
    for spec in re.findall(r"""(?:from|import\()\s*["']([^"']+)["']""", text):
        if spec.startswith("@/"):
            base = SRC / spec[2:]
        elif spec.startswith("."):
            base = (path.parent / spec).resolve()
        else:
            continue
        found = _resolve(base)
        if found:
            yield found


def _walk(files):
    seen, queue = set(), list(files)
    while queue:
        f = queue.pop()
        if f in seen:
            continue
        seen.add(f)
        queue.extend(imports(f))
    return seen


def _route_components():
    app = (SRC / "App.js").read_text()
    names: dict[str, str] = {}
    for name, spec in re.findall(
        r"const (\w+) = load\(\(\)\s*=>\s*import\(\s*(?:/\*[^*]*\*/\s*)?\"(@/[^\"]+)\"", app, flags=re.S
    ):
        names[name] = spec
    admin_spec = re.search(r"const adminRoute = .*?import\(\s*(?:/\*[^*]*\*/\s*)?\"(@/[^\"]+)\"", app, flags=re.S)
    if admin_spec:
        for name in re.findall(r"const (\w+) = adminRoute\(", app):
            names[name] = admin_spec.group(1)
    for group, spec in re.findall(r'import \{([^}]+)\} from "(@/[^"]+)"', app):
        for n in re.split(r"[,\s]+", group):
            if n:
                names.setdefault(n.split(" as ")[-1], spec)
    for name, spec in re.findall(r'import (\w+) from "(@/[^"]+)"', app):
        names.setdefault(name, spec)

    body = app[app.index("<Routes>"):]
    app_side, public_side = set(), set()
    for block in re.split(r"\n {24}<Route\b", body)[1:]:
        m = re.search(r'path="([^"]+)"', block)
        path = m.group(1) if m else "*"
        comps = set(re.findall(r"<([A-Z]\w+)", block)) - {"Route", "ProtectedRoute", "Navigate", "Suspense"}
        (app_side if is_app_path(path) else public_side).update(comps)

    def files(comps):
        out = set()
        for c in comps:
            spec = names.get(c)
            if spec and (f := _resolve(SRC / spec[2:])):
                out.add(f)
        return out

    shell = set()
    for spec in re.findall(r'^import [^;]*? from "(@/[^"]+)";', app, flags=re.M):
        if f := _resolve(SRC / spec[2:]):
            shell.add(f)
    return files(app_side), files(public_side) | shell, app_side


_APP_ROOTS, _PUBLIC_ROOTS, APP_ROUTE_COMPONENTS = _route_components()
_APP = _walk(_APP_ROOTS)
_PUBLIC = _walk(_PUBLIC_ROOTS)

APP_ONLY = sorted(f for f in _APP - _PUBLIC if "__tests__" not in f.parts and ".test." not in f.name)
SHARED = sorted(f for f in _APP & _PUBLIC if "__tests__" not in f.parts and ".test." not in f.name)
