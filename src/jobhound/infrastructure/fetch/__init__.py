"""Fetching a posting URL's HTML.

Two tiers: an unauthenticated HTTP GET (`http_fetch`), falling back to a
persistent authenticated browser profile (`browser_fetch`) only when the
cheap path hits an auth wall. `base` holds the shared result type and
error taxonomy.
"""
