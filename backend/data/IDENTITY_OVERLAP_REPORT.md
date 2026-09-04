# Identity-Overlap Analysis Report: Backend Models (Schema A) vs. Frontend Schemas (Schema B)

**Date**: September 4, 2026  
**Target Repository**: Dark Knight Law-Enforcement Intelligence Platform (`Chandigarh-Police-1st-MVP`)  
**Investigated Schemas**:
- **Schema A (Database / Ingestion)**: `backend/models.py` (SQLAlchemy ORM models in `backend/darknight.db`)
- **Schema B (Network Viz / Geo Analytics)**: `backend/data/schemas.py` & `backend/synthetic_data.py` (Pydantic DTOs & synthetic mock entities)

---

## Executive Summary & Classification

### Category Conclusion: **b) WEAK / PARTIAL OVERLAP**

- **Conceptual Alignment**: Both schemas describe the exact same real-world domain: suspects, cryptocurrency wallets, transactions, market accounts, and activity observations.
- **Identifier Value Disconnect**: In the actual codebase, zero directly matchable identifier strings exist between Daksh's dataset (`backend/synthetic_data.py`) and the real database dataset (`backend/darknight.db`). Daksh's dataset uses synthetic mock strings (e.g., `"abc123"`, `"bc1qxxxxxxx1"`), whereas the backend database contains real-world law-enforcement intelligence (OFAC SDN sanctioned targets, real Bitcoin blockchain addresses, Agora darknet listings).
- **Implication**: Unification cannot be achieved via simple SQL database join queries; it requires a canonical mapping adapter / transformation layer that maps real-world models into the unified entity graph.

---

## 1. Side-by-Side ID & Identifier-Like Field Comparison

| Schema B Field (`data/schemas.py`) | Type | Schema A Field (`models.py`) | Type | Equivalence & Notes |
| :--- | :--- | :--- | :--- | :--- |
| `Entity.id` | `str` | `Suspect.id`<br>`CryptoWallet.id`<br>`DarknetListing.id`<br>`TelegramChannel.id` | `int` (PK) | Direct entity primary key. Schema B uses string IDs (`"suspect_1"`, `"wallet_5"`), Schema A uses auto-incrementing integers. |
| `Entity.identifier` | `str` | `CryptoWallet.address`<br>`Suspect.primary_alias`<br>`Suspect.telegram_handle`<br>`DarknetListing.url`<br>`TelegramChannel.channel_id` | `str` | Unique real-world identifier string (Bitcoin address, Telegram handle, vendor alias, URL). |
| `Entity.type` | `EntityType` (Enum) | Model class (`Suspect`, `CryptoWallet`, `DarknetListing`, `TelegramChannel`) | Class | Categorical taxonomy. Schema B uses an Enum (`suspect`, `wallet`, `market`, `account`), Schema A uses separate relational tables. |
| `Entity.platform` | `Optional[str]` | `DarknetListing.platform`<br>`CryptoWallet.currency`<br>Hardcoded `"Telegram"` / `"Blockchain"` | `str` | Originating network or marketplace platform. |
| `Transaction.id` | `str` | `CryptoTransaction.id` | `int` (PK) | Transaction event identifier. |
| `Transaction.source_entity` | `str` | `CryptoTransaction.from_address` | `str` | Source endpoint of a financial transfer or relationship edge. |
| `Transaction.target_entity` | `str` | `CryptoTransaction.to_address` | `str` | Destination endpoint of a financial transfer or relationship edge. |
| `Observation.id` | `str` | `TelegramMessage.id`<br>`NetworkTrafficFlow.id` | `int` (PK) / `str` | Event or log entry identifier. |
| `Observation.entity_id` | `str` | `TelegramMessage.channel_id`<br>`TelegramMessage.sender_handle`<br>`NetworkTrafficFlow.src_ip` | `int` / `str` | Foreign key binding event observation to an entity node. |
| `Region.id` / `DetailedLocation.id` | `str` | `DarknetListing.location` | `str` | Spatial / geographic location entity. |

---

## 2. Sample Data Comparison (5–10 Records per Side)

### Schema B Data Sample (`backend/synthetic_data.py`)

1. **Entity (Suspect)**:
   - `id`: `"suspect_1"` | `type`: `"suspect"` | `identifier`: `"abc123"` | `platform`: `"Encrypted Forum Z"` | `display_name`: `"abc123"`
2. **Entity (Account Alias)**:
   - `id`: `"account_1a"` | `type`: `"account"` | `identifier`: `"123_abc"` | `platform`: `"Telegram"` | `display_name`: `"123_abc"`
3. **Entity (Wallet)**:
   - `id`: `"wallet_1"` | `type`: `"wallet"` | `identifier`: `"bc1qxxxxxxx1"` | `platform`: `"Blockchain"` | `display_name`: `"Wallet 1"`
4. **Entity (Marketplace)**:
   - `id`: `"mkt_alpha"` | `type`: `"market"` | `identifier`: `"AlphaBay (Reborn)"` | `platform`: `"AlphaBay (Reborn)"` | `display_name`: `"AlphaBay (Reborn)"`
5. **Transaction**:
   - `id`: `"tx_15"` | `source_entity`: `"wallet_5"` | `target_entity`: `"wallet_9"` | `amount`: `0.1425 BTC` | `timestamp`: `2026-08-18 09:00:00`
6. **Observation**:
   - `id`: `"obs_1"` | `entity_id`: `"suspect_1"` | `source`: `"Telegram"` | `activity_type`: `"listing_post"` | `lat/lon`: `(30.7410, 76.7822)` (Chandigarh)

### Schema A Data Sample (`backend/darknight.db`)

1. **Suspect (`suspects`)**:
   - `id`: `3` | `primary_alias`: `"SUEX OTC"` | `telegram_handle`: `None` | `pgp_fingerprint`: `None` | `risk_score`: `95`
2. **Suspect (`suspects`)**:
   - `id`: `8` | `primary_alias`: `"LIFSHITS"` | `telegram_handle`: `None` | `pgp_fingerprint`: `None` | `risk_score`: `95`
3. **Crypto Wallet (`crypto_wallets`)**:
   - `id`: `1` | `address`: `"112FBwDQ21CYxX785HE8qnQwkoDusYsTxC"` | `currency`: `"BTC"` | `risk_level`: `"ILLICIT"` | `associated_suspect_id`: `None`
4. **Crypto Wallet (`crypto_wallets`)**:
   - `id`: `4` | `address`: `"12M3KnryJcWoU2KRmcXEcNY38t7tUJwPeh"` | `currency`: `"BTC"` | `risk_level`: `"ILLICIT"` | `associated_suspect_id`: `None`
5. **Crypto Transaction (`crypto_transactions`)**:
   - `id`: `1` | `tx_hash`: `"07fb6c51d2fba7ed9c7da44502edae0e177fed6b4244f4164a147ce2ecae6dc1"` | `from_address`: `"1PNZcSjziHuKEKgoTAWVtCt7oUAcRLQQAC"` | `to_address`: `"18k2TA54KSLe6rGGWZVc3w42kYHRwSGVBT"` | `amount`: `"UNSPECIFIED"`
6. **Darknet Listing (`darknet_listings`)**:
   - `id`: `1` | `title`: `"Sample Cannabis Batch listing #1001"` | `vendor_alias`: `"AlphaVendor"` | `platform`: `"Agora"` | `price`: `"0.3321 BTC"`
7. **Telegram Message (`telegram_messages`)**:
   - `id`: `4` | `channel_id`: `4` | `sender_handle`: `"@SecurityMonitor_CDG"` | `message_text`: `"Network Warning: Suspicious transaction pattern detected on wallet address 1LiNmTUPSJEd92ZgVJjAV3RT9BzUjvUCkx."`

---

## 3. Cross-Check & Overlap Findings

### A. Identifier String Cross-Check (Exact Join Test)

An automated cross-check script was executed against the database:
- **Synthetic Identifiers in Schema B**: 34 unique string identifiers (e.g. `"abc123"`, `"bc1qxxxxxxx1"`, `"vendor_55"`).
- **Real Identifiers in Schema A**:
  - `crypto_wallets.address`: 924 real Bitcoin wallet addresses
  - `crypto_transactions.from/to_address`: 392 unique blockchain addresses
  - `suspects.primary_alias`: 87 suspect aliases
  - `darknet_listings.vendor_alias`: 10 Agora vendor aliases
  - `telegram_channels.channel_name`: 20 channel handles
- **Result**: **0 exact matches** and **0 substring/fuzzy matches**.

### B. Taxonomy Alignment

| Schema B `EntityType` | Corresponding Schema A Concept | Alignment Status |
| :--- | :--- | :--- |
| `suspect` | `models.Suspect` | **100% Concept Overlap** (models sanctioned individuals / target suspects) |
| `wallet` | `models.CryptoWallet` | **100% Concept Overlap** (models cryptocurrency addresses) |
| `market` | `models.DarknetListing.platform` / `models.TelegramChannel` | **Partial Concept Overlap** (Schema B treats markets as nodes; Schema A models market listings as items & channels as chat groups) |
| `account` | `models.DarknetListing.vendor_alias` / `TelegramMessage.sender_handle` | **Partial Concept Overlap** (Schema B treats platform accounts as separate nodes from suspects; Schema A attributes aliases directly to `Suspect`) |

---

## 4. Conclusion & Recommended Action

The two schemas represent **WEAK / PARTIAL OVERLAP**:
1. They are structurally ready to be unified because every concept in Schema B (`Entity`, `Transaction`, `Observation`) maps cleanly onto one or more tables in Schema A (`Suspect`, `CryptoWallet`, `CryptoTransaction`, `DarknetListing`, `TelegramMessage`).
2. They do not share identical seed values because Schema B relied on synthetic mock generators (`synthetic_data.py`), whereas Schema A was populated with real OFAC, Elliptic++, Agora, and Telegram dataset pipelines.

### Recommendation
Implement a **Graph Adapter** in `backend/graph_adapter.py` that dynamically transforms real database models (`backend/models.py`) into canonical `Entity`, `Transaction`, and `Observation` DTOs (`backend/data/schemas.py`). This allows the frontend network visualization and hotspot heatmaps to render live production data seamlessly.
