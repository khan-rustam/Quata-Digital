"""The import boundary is a test, not a convention.

"Only QCP talks to Meta, and inside QCP only one module does" is the property
the whole platform rests on. A comment cannot enforce it and a code review
will eventually miss it, so it is asserted mechanically here: walk the source
tree and check who is allowed to reach the transport.

If one of these fails, someone has opened a second path to Meta — which means
the account-purpose invariant can be bypassed by not going through
``resolve_route`` at all.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


APP_ROOT = Path(__file__).resolve().parent.parent / "app"
WA_PACKAGE = APP_ROOT / "services" / "whatsapp"

# Matches the ways a module can get its hands on the transport:
#   from .meta import send_template     /    from . import meta
#   from app.services.whatsapp.meta import ...
#   import app.services.whatsapp.meta
_IMPORTS_META = re.compile(
    r"from\s+\.meta\s+import|from\s+app\.services\.whatsapp\.meta|import\s+.*\bmeta\b"
)
_REFERENCES_META = re.compile(r"app\.services\.whatsapp\.meta")


def _python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_docstrings_and_comments(source: str) -> str:
    """Crude but sufficient: drop triple-quoted blocks and ``#`` comments.

    Every module here documents the boundary in prose, and prose naming
    ``meta`` must not read as an import.
    """
    without_docstrings = re.sub(r'"""(?:.|\n)*?"""', "", source)
    without_docstrings = re.sub(r"'''(?:.|\n)*?'''", "", without_docstrings)
    return re.sub(r"#.*", "", without_docstrings)


def test_only_dispatch_may_import_the_meta_transport():
    offenders = set()
    for path in _python_files(APP_ROOT):
        code = _strip_docstrings_and_comments(_source(path))
        inside_package = WA_PACKAGE in path.parents
        if _REFERENCES_META.search(code) or (inside_package and _IMPORTS_META.search(code)):
            offenders.add(path.name)
    offenders.discard("meta.py")  # the transport itself
    assert offenders == {"dispatch.py"}, (
        "Exactly one module may reach the Meta transport. Found: " f"{sorted(offenders)}"
    )


def test_the_graph_api_host_is_known_to_exactly_one_module():
    """One place knows Meta's address, and one module dials it.

    The literal host lives in ``core/config.py`` as ``WHATSAPP_GRAPH_BASE``
    (env-overridable, no secret), so the QCP package itself contains no
    hard-coded endpoint at all. What the boundary requires is that exactly
    one module in the package *reads* that base URL — a second reader would
    be a second HTTP client.
    """
    literal = [p.name for p in _python_files(APP_ROOT) if "graph.facebook.com" in _source(p)]
    assert literal == ["config.py"]

    readers = [
        p.name for p in _python_files(WA_PACKAGE) if "WHATSAPP_GRAPH_BASE" in _source(p)
    ]
    assert readers == ["meta.py"]


def test_every_send_call_site_lives_in_dispatch():
    call_sites = set()
    for path in _python_files(APP_ROOT):
        code = _strip_docstrings_and_comments(_source(path))
        if re.search(r"\bmeta\.send_(template|text)\s*\(", code):
            call_sites.add(path.name)
    assert call_sites == {"dispatch.py"}


def test_routing_never_reaches_the_network():
    """``routing.py`` is the choke point; it must not be able to send.

    If it could import the transport, a future edit could resolve *and*
    deliver in one step, and the "insert the row before you send" ordering
    that makes duplicates and crashes recoverable would quietly disappear.
    """
    code = _strip_docstrings_and_comments(_source(WA_PACKAGE / "routing.py"))
    assert not _IMPORTS_META.search(code)
    assert "dispatch" not in code


@pytest.mark.parametrize("module", ["webhooks.py", "conversations.py", "registry.py", "templates.py"])
def test_sibling_modules_do_not_import_the_transport(module):
    path = WA_PACKAGE / module
    if not path.exists():
        pytest.skip(f"{module} is not part of this build")
    assert not _IMPORTS_META.search(_strip_docstrings_and_comments(_source(path)))


def test_the_facade_is_the_only_entry_point_for_other_packages():
    """Nothing outside ``app/services/whatsapp`` may import a submodule.

    Routers and scripts import the package (or, where a lazy import is
    needed, ``dispatch`` — the documented worker entry point). Reaching past
    that into ``routing`` or ``meta`` from elsewhere would let a caller mint
    or bypass a ticket.
    """
    allowed = {"app.services.whatsapp.dispatch"}
    pattern = re.compile(r"from\s+app\.services\.whatsapp\.(\w+)|app\.services\.whatsapp\.(\w+)")
    offenders: list[str] = []
    for path in _python_files(APP_ROOT):
        if WA_PACKAGE in path.parents:
            continue
        code = _strip_docstrings_and_comments(_source(path))
        for match in pattern.finditer(code):
            submodule = match.group(1) or match.group(2)
            if f"app.services.whatsapp.{submodule}" not in allowed:
                offenders.append(f"{path.name}: {submodule}")
    assert offenders == [], f"Import the package facade, not its internals: {offenders}"
