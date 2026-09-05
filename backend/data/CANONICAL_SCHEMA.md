# Canonical Schema Architecture & Field Lineage Documentation

**Version**: 1.0.0  
**Target Repository**: Dark Knight Law-Enforcement Intelligence Platform (`Chandigarh-Police-1st-MVP`)  
**Core File**: `backend/data/canonical_schema.py`

---

## 1. Executive Summary & Design Principles

The **Canonical Schema** unifies all disparate data representations in the project into a single, standardized object graph built around three fundamental buckets:
- **Things (`CanonicalEntity`)**: Suspects, crypto wallets, marketplace listings, Telegram channels, market accounts, organization entities, and IP network nodes.
- **Connections (`CanonicalTransaction`)**: Financial transactions, suspect ownership links, seller-listing relationships, and network node edges.
- **Events (`CanonicalObservation`)**: Timestamped observations, Telegram messages, network flow telemetry, spatial location pings, and log events.

Spatial reference structures (`BoundingBox`, `CanonicalRegion`, `CanonicalDetailedLocation`) are retained as top-level reference data models.

---

## 2. Field Lineage & Source Justification

Every top-level field in `canonical_schema.py` is explicitly derived from existing models in `backend/models.py` (Schema A) or `backend/data/schemas.py` (Schema B). Below is the complete field-by-field lineage audit:

### A. `CanonicalEntity` Fields

| Field Name | Type | Source Model & Field | Justification & Domain Purpose |
| :--- | :--- | :--- | :--- |
| `id` | `str` | `Entity.id` (Schema B)<br>`Suspect.id`, `CryptoWallet.id`, `DarknetListing.id` (Schema A) | Unique identifier string (e.g. `"suspect_1"`, `"wallet_924"`). |
| `type` | `EntityType` | `Entity.type` (Schema B)<br>Model Class names (Schema A) | Extensible discriminator (`suspect`, `wallet`, `market`, `listing`, `channel`, `account`, `ip_node`). |
| `identifier` | `str` | `Entity.identifier` (Schema B)<br>`CryptoWallet.address`, `Suspect.primary_alias`, `DarknetListing.url`, `TelegramChannel.channel_id` (Schema A) | **Unique constraint & indexed**. Primary domain string (Bitcoin address, handle, URL). Used for cross-source entity deduplication and collision logging. |
| `display_name` | `Optional[str]` | `Entity.display_name` (Schema B)<br>`Suspect.primary_alias`, `DarknetListing.title`, `TelegramChannel.channel_name` (Schema A) | Human-readable UI label. |
| `platform` | `Optional[str]` | `Entity.platform` (Schema B)<br>`DarknetListing.platform` ("Agora"), Telegram ("Telegram"), Blockchain ("Blockchain") (Schema A) | Originating market or messaging platform name. |
| `location` | `Optional[str]` | `Entity.location` (Schema B)<br>`DarknetListing.location` (Schema A) | Descriptive location text. |
| `risk_score` | `int` | `Suspect.risk_score` (Schema A, 0-100)<br>Mapped from `CryptoWallet.risk_level` (Schema A) | Quantitative risk metric (0-100) required for critical alerts and investigative scoring. |
| `created_at` | `datetime` | `Entity.created_at` (Schema B)<br>`Suspect.created_at`, `DarknetListing.scraped_at` (Schema A) | UTC creation or scraping timestamp. |
| `updated_at` | `Optional[datetime]` | `Suspect.updated_at` (Schema A) | Entity state modification timestamp for audit tracking. |
| `metadata` | `Dict[str, Any]` | `Observation.metadata` (Schema B)<br>`Suspect.aliases_json`, `Suspect.pgp_fingerprint`, `Suspect.phone_number`, `Suspect.notes`, `CryptoWallet.balance`, `CryptoWallet.risk_level`, `DarknetListing.description`, `DarknetListing.price`, `DarknetListing.drug_category` (Schema A) | JSON dictionary preserving all domain-specific extra fields without schema degradation. |

---

### B. `CanonicalTransaction` Fields

| Field Name | Type | Source Model & Field | Justification & Domain Purpose |
| :--- | :--- | :--- | :--- |
| `id` | `str` | `Transaction.id` (Schema B)<br>`CryptoTransaction.id` (Schema A) | Unique transaction/relationship identifier string. |
| `tx_hash` | `Optional[str]` | `CryptoTransaction.tx_hash` (Schema A) | Blockchain transaction hash string (64-char hex) when representing crypto transfers. |
| `source_entity_id` | `str` | `Transaction.source_entity` (Schema B)<br>`CryptoTransaction.from_address` (Schema A) | Source node identifier or entity ID. |
| `target_entity_id` | `str` | `Transaction.target_entity` (Schema B)<br>`CryptoTransaction.to_address` (Schema A) | Destination node identifier or entity ID. |
| `amount` | `float` | `Transaction.amount` (Schema B)<br>Parsed from `CryptoTransaction.amount` (Schema A) | Numeric transfer amount for graph edge weight calculation. |
| `amount_str` | `Optional[str]` | `CryptoTransaction.amount` (Schema A) | Retains the exact raw string representation (e.g. `"UNSPECIFIED"`, `"0.045 BTC"`). |
| `currency` | `str` | `Transaction.currency` (Schema B)<br>`CryptoTransaction.currency` (Schema A) | Currency code (default `"BTC"`). |
| `timestamp` | `datetime` | `Transaction.timestamp` (Schema B)<br>`CryptoTransaction.timestamp` (Schema A) | Transaction occurrence datetime in UTC. |
| `metadata` | `Dict[str, Any]` | N/A | Extensible JSON container for fee structure, block height, or edge attributes. |

---

### C. `CanonicalObservation` Fields

| Field Name | Type | Source Model & Field | Justification & Domain Purpose |
| :--- | :--- | :--- | :--- |
| `id` | `str` | `Observation.id` (Schema B)<br>`TelegramMessage.id`, `NetworkTrafficFlow.id` (Schema A) | Event observation string identifier. |
| `entity_id` | `str` | `Observation.entity_id` (Schema B)<br>`TelegramMessage.channel_id`, `TelegramMessage.sender_handle`, `NetworkTrafficFlow.src_ip` (Schema A) | FK binding observation to a `CanonicalEntity`. |
| `source` | `str` | `Observation.source` (Schema B)<br>`"Telegram"`, `"NetworkFlow"` (Schema A) | Sensor/platform source string. |
| `timestamp` | `datetime` | `Observation.timestamp` (Schema B)<br>`TelegramMessage.timestamp`, `NetworkTrafficFlow.timestamp_str` (Schema A) | UTC observation timestamp. |
| `latitude` | `Optional[float]` | `Observation.latitude` (Schema B) | Geographic latitude coordinate. |
| `longitude` | `Optional[float]` | `Observation.longitude` (Schema B) | Geographic longitude coordinate. |
| `region` | `Optional[str]` | `Observation.region` (Schema B) | Region identifier string (e.g., `"chandigarh"`). |
| `activity_type` | `str` | `Observation.activity_type` (Schema B)<br>`"telegram_message"`, `"network_flow"` (Schema A) | **Free string** discriminator (e.g. `telegram_message`, `network_flow`, `location_ping`, `darknet_scrape`). Requires no code changes when adding new event types. |
| `risk_signal` | `Optional[str]` | `Observation.risk_signal` (Schema B)<br>Detected keyword match flag from `TelegramMessage` (Schema A) | Text signal indicating potential illicit activity. |
| `metadata` | `Dict[str, Any]` | `Observation.metadata` (Schema B)<br>`TelegramMessage.message_text`, `TelegramMessage.detected_wallets_json`, `TelegramMessage.detected_keywords_json`, `NetworkTrafficFlow.src_port`, `NetworkTrafficFlow.dst_ip`, `NetworkTrafficFlow.dst_port`, `NetworkTrafficFlow.protocol`, `NetworkTrafficFlow.encapsulation_label`, `NetworkTrafficFlow.application_label`, `NetworkTrafficFlow.is_encrypted` (Schema A) | Full unstructured event payload container. |

---

## 3. Merging & Extension Logic

### 1. `EntityType` Open Enum
`EntityType` inherits from `str, Enum` and implements a `_missing_` handler. When an incoming dataset contains a newly discovered category (e.g. `telecom_tower`), it is dynamically instantiated as a valid member without crashing validation routines.

### 2. `Entity.identifier` Uniqueness & Collision Logging
- `Entity.identifier` is enforced with a database `UNIQUE` constraint and index.
- When an ingestion pipeline encounters an existing `identifier` (e.g. the same Bitcoin wallet address from two different sources), it performs an **upsert**:
  - Top-level risk scores are updated to the maximum risk across sources.
  - Source data is merged into `metadata_json["sources"]`.
  - **High-Visibility Collision Logging**: Every collision is logged to `identifier_collisions.log` and prominently highlighted in the ingestion execution summary output.

### 3. Non-Lossy Metadata Fallback
No input data field is ever dropped. Any field that does not map directly to a top-level column is placed inside `metadata_json`.
