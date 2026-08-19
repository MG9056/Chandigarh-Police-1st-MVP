# DarKnight MVP - Project Journal

## Initial Scaffolding Phase (Completed)

**Features Built:**
1. **Backend Skeleton**: Set up FastAPI and Uvicorn inside `backend/` directory. Added a dummy `main.py` file with mock JSON endpoints: `/api/dashboard/summary`, `/api/alerts`, and `/api/network/data` to simulate an active database for the MVP.
2. **Frontend Skeleton**: Created a Vite React application inside `frontend/`. 
3. **Tailwind CSS & Shadcn UI**: Initialized Tailwind CSS and Shadcn UI manually, and correctly mapped CSS variables to the `tailwind.config.js` to ensure Shadcn components (like `Button`) compile without errors.
4. **Localization (i18n)**: Implemented `react-i18next` with three languages (English, Hindi, Punjabi). Created a language switcher in the navbar.
5. **Light/Dark Mode**: Created a `theme-provider.jsx` Context to toggle between light and dark modes globally.
6. **Bootup Animation**: Implemented a Matrix-style "flying 0s and 1s" animation using `framer-motion` alongside a rotating Chandigarh Police logo (`cdg-logo.png`). The animation lasts ~3 seconds before revealing the dashboard.
7. **3-Panel Dashboard Layout**: Created the primary UI skeleton in `App.jsx` consisting of:
   - Left Panel: General Information navigation.
   - Middle Panel: Main details/metrics overview.
   - Right Panel: Deep-dive/System status indicators.

**Mistakes Made & Fixed:**
- **Tailwind/Shadcn Init Bug**: The default Shadcn CLI failed due to Vite React resolving issues with Tailwind v4. **Fix**: Downgraded Tailwind to v3, manually created `jsconfig.json` with path aliases, and manually added the required UI dependencies.
- **CSS Variable Compilation Error**: The `index.css` used `@apply border-border` which caused a Vite PostCSS crash (`border-border` class did not exist) because the `tailwind.config.js` was missing the `theme.extend.colors` mapping for Shadcn. **Fix**: Updated `tailwind.config.js` to map `border: "hsl(var(--border))"` and other Shadcn standard color variables.

**Phase 2: Specific Features Implementation (Completed)**

**Features Built:**
1. **Interactive Intelligence Dashboard (`DashboardOverview.jsx`)**: Displays active investigations, critical alerts, and monitored sources metrics using mock data from the backend.
2. **Data Collection Status (`DataCollectionStatus.jsx`)**: Shows the status of various data scraper nodes (e.g. Darknet Market Alpha, BTC Blockchain Node) along with last sync times and simulated pulse animations.
3. **Alerts & Suspicious Activity (`AlertsFeed.jsx`)**: Consolidates automated alerts (red/yellow/green severity) and AI-driven suspicious activity detection (keyword matching, pattern anomalies) using FastAPI endpoints.
4. **Network Visualization (`NetworkGraph.jsx`)**: Integrated `react-force-graph-2d` to render a dynamic, physics-based network graph identifying correlations between suspects, cryptocurrency wallets, and digital marketplaces. Nodes are color-coded and fully interactive.
5. **Search & Investigation (`SearchInvestigation.jsx`)**: Added a search bar with mock filtering across aliases, wallets, and keywords, complete with risk score indicators.
6. **Reports & Evidence (`ReportingEvidence.jsx`)**: Simulated a table interface for viewing drafted and finalized intelligence reports, complete with mock PDF download buttons.
7. **Security & Access Control (`AccessControl.jsx`)**: Created an investigator profile panel detailing clearance levels, secure connection status, and mock settings for Role Management and Audit Logs.

**Mistakes Made & Fixed:**
- N/A for this phase. The frontend routing and component integration proceeded smoothly.

**Phase 3: UI/UX Refinements (Completed)**

**Features Built:**
1. **Search Default State**: Modified `SearchInvestigation.jsx` to fetch and display default search results immediately on mount, providing instant context without requiring an initial manual query.
2. **Bootup Sequence Optimization**: Adjusted `BootupAnimation.jsx` so the police logo stays centered (instead of spinning) and morphs seamlessly into the matrix effect. Added a smooth opacity fade-out on the animation container before transitioning into the main dashboard.
3. **Network Graph Physics Strictness**: Updated the `react-force-graph-2d` instance in `NetworkGraph.jsx` using `d3Force` adjustments (stronger negative charge and longer link distances). This ensures nodes have clear demarcations and prevents overlapping, making the relationships easier to read.

**Next Steps (Comparing to To-do.md):**
- **To-do.md is now fully implemented** for the MVP scope on the frontend. All 9 specified dashboard features are complete with mock data logic, and all visual refinements have been applied. We can now safely clear these completed items from the `To-do.md` list, as real backend integration is planned for a later phase.

**Phase 4: Rebranding and Interactivity (Completed)**

**Features Built:**
1. **App Renaming**: Renamed the application from "Kala Jaddu" to "DarKnight" across all frontend views, navigation headers, i18n translation files, and backend API titles.
2. **Bootup Morphing**: Updated `BootupAnimation.jsx` so the logo performs a 3D bit-flip effect (rotating on the Y-axis and scaling down) to visually "morph" into the matrix of 0s and 1s.
3. **Graph Interactivity & Controls**: In `NetworkGraph.jsx`:
   - Added Zoom In, Zoom Out, and Zoom-to-Fit controls.
   - Added an Expand button to make the graph fill the screen (leaving the sidebar intact).
   - Added automatic `zoomToFit` on initial data load for optimal at-a-glance viewing.
   - Implemented highlighting: hovering or clicking a node dims all unrelated nodes and highlights direct connections and paths in red.
