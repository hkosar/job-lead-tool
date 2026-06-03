"""Adapter registry. To add a source: write an adapter file, import it, add to REGISTRY."""
from .adzuna import AdzunaAdapter
from .greenhouse import GreenhouseAdapter
from .lever import LeverAdapter
from .usajobs import UsaJobsAdapter
from .serpapi_googlejobs import SerpApiGoogleJobsAdapter
from .indeed_vendor import IndeedVendorAdapter

REGISTRY = {a.key: a() for a in [
    AdzunaAdapter, GreenhouseAdapter, LeverAdapter,
    UsaJobsAdapter, SerpApiGoogleJobsAdapter, IndeedVendorAdapter,
]}
