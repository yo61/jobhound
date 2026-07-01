"""HTML → ScrapedJob extractors.

Pure functions over page HTML, one per site shape. LinkedIn uses a
custom extractor (`linkedin`); sites that publish schema.org JobPosting
JSON-LD use the generic `jsonld` extractor. `registry` routes by hostname.
"""
