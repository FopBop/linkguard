#!/usr/bin/env python3
"""End-to-end demonstration of FEATURE 2 - broken-link detection.

Runs the real ``classify`` function against a small local fixture: a tiny
Markdown document plus an in-process HTTP server on loopback. Prints a
pass/fail verdict per link so the success criterion ("running the feature
against a small local fixture produces correct pass/fail results for reachable
and unreachable links") can be observed directly.

Usage::

    python3 tests/demo_broken_links.py

Exit status is 0 when every link is classified as expected, 1 otherwise.
"""

import importlib.util
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

_spec = importlib.util.spec_from_file_location(
    "linkguard_core", os.path.join(_ROOT, "linkguard.py"))
lg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lg)


class _Handler(BaseHTTPRequestHandler):
    """Serve /reachable -> 200 and /missing -> 404."""

    def log_message(self, *args):  # keep demo output clean
        pass

    def _respond(self):
        if self.path.startswith("/reachable"):
            self.send_response(200)
        else:
            self.send_response(404)
        self.end_headers()

    def do_HEAD(self):
        self._respond()

    def do_GET(self):
        self._respond()


def _start_server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever)
    thread.daemon = True
    thread.start()
    return httpd, httpd.server_address[1]


def main():
    fixtures = os.path.join(_HERE, "fixtures")
    httpd, port = _start_server()
    base = "http://127.0.0.1:%d" % port
    try:
        cases = [
            # (url, expected_status, label)
            ("doc_with_headings.md", "ok", "existing local file"),
            ("missing-doc.md", "broken", "missing local file"),
            ("doc_with_headings.md#advanced-usage", "ok", "existing anchor"),
            ("doc_with_headings.md#nope", "broken", "missing anchor"),
            ("%s/reachable" % base, "ok", "reachable remote (HTTP 200)"),
            ("%s/missing" % base, "broken", "unreachable remote (HTTP 404)"),
            ("mailto:a@b.com", "skipped", "non-navigable scheme"),
        ]
        failures = 0
        print("broken-link detection demo (offline loopback fixture)")
        print("-" * 60)
        for url, expected, label in cases:
            link = lg.Link(url, 1, 1)
            lg.classify(link, allow_network=True, timeout=5.0,
                        base_dir=fixtures)
            ok = link.status == expected
            failures += 0 if ok else 1
            print("%-4s %-34s -> %-7s (expected %s)%s" % (
                "PASS" if ok else "FAIL", label, link.status, expected,
                "" if ok else "  [%s]" % (link.error or "")))
        print("-" * 60)
        print("%d case(s), %d failure(s)" % (len(cases), failures))
        return 1 if failures else 0
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    sys.exit(main())
