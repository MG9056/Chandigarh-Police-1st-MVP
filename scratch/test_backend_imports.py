import sys
import os

backend_dir = r"c:\Users\shrih\Desktop\lmaoded\Chandigarh-Police-1st-MVP\backend"
sys.path.insert(0, backend_dir)

print("=== TESTING ACTUAL CRAWLER & BACKEND MODULE IMPORTS ===")

actual_crawler_modules = [
    "crawler.models",
    "crawler.models.source",
    "crawler.models.keyword",
    "crawler.models.case_keyword",
    "crawler.models.crawler_run",
    "crawler.models.raw_record",
    "crawler.models.robots_cache",
    "crawler.policy.robots_checker",
    "crawler.policy.rate_limiter",
    "crawler.collectors.base",
    "crawler.collectors.bitcoin",
    "crawler.collectors.direct_seed",
    "crawler.collectors.google_discovery",
    "crawler.collectors.registry",
    "crawler.collectors.telegram",
    "crawler.collectors.tor_stub",
    "crawler.collectors.transport",
    "crawler.pipeline.cleaner",
    "crawler.pipeline.dedup",
    "crawler.pipeline.entity_extractor",
    "crawler.pipeline.language",
    "crawler.pipeline.relevance_classifier",
    "crawler.pipeline.relevance_filter",
    "crawler.evidence.tagging",
    "crawler.keywords.service",
    "crawler.orchestration.flows",
    "crawler.orchestration.scheduler",
    "crawler.api.routers.sources",
    "crawler.api.routers.keywords",
    "crawler.api.routers.raw_records",
    "crawler.api.routers.activity",
]

failed_imports = []

for mod in actual_crawler_modules:
    try:
        __import__(mod)
        print(f"  [OK] {mod}")
    except Exception as e:
        print(f"  [FAILED] {mod} -> {type(e).__name__}: {e}")
        failed_imports.append((mod, str(e)))

print(f"\nTotal crawler modules tested: {len(actual_crawler_modules)}")
print(f"Passed: {len(actual_crawler_modules) - len(failed_imports)}")
print(f"Failed: {len(failed_imports)}")

if failed_imports:
    print("\nFailed Crawler Imports Summary:")
    for mod, err in failed_imports:
        print(f"  - {mod}: {err}")
