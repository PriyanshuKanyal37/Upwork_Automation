# Graph Report - C:\Users\priya\Desktop\Ladder\Upwork_automation\frontend  (2026-04-30)

## Corpus Check
- Corpus is ~24,108 words - fits in a single context window. You may not need a graph.

## Summary
- 154 nodes · 223 edges · 22 communities detected
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 37 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Approvejob Beautifymanualprofile|Approvejob Beautifymanualprofile]]
- [[_COMMUNITY_Createproject Listprojects|Createproject Listprojects]]
- [[_COMMUNITY_Getjobdetail Listgenerationruns|Getjobdetail Listgenerationruns]]
- [[_COMMUNITY_Createprofile Login|Createprofile Login]]
- [[_COMMUNITY_Handleextract Extractupworkprofile|Handleextract Extractupworkprofile]]
- [[_COMMUNITY_Logout Clearcurrentjobid|Logout Clearcurrentjobid]]
- [[_COMMUNITY_Listconnectors Startgoogleoauth|Listconnectors Startgoogleoauth]]
- [[_COMMUNITY_React Eslint|React Eslint]]
- [[_COMMUNITY_Workflowvisualizer N8nlogo|Workflowvisualizer N8nlogo]]
- [[_COMMUNITY_Jobtitles Derivejobtitle|Jobtitles Derivejobtitle]]
- [[_COMMUNITY_Jobsdashboardpage Fnum|Jobsdashboardpage Fnum]]
- [[_COMMUNITY_Usagepage Fnum|Usagepage Fnum]]
- [[_COMMUNITY_Brandwordmark|Brandwordmark]]
- [[_COMMUNITY_Apirequesterror Constructor|Apirequesterror Constructor]]
- [[_COMMUNITY_Placeholderpage|Placeholderpage]]
- [[_COMMUNITY_Postcss|Postcss]]
- [[_COMMUNITY_Tailwind|Tailwind]]
- [[_COMMUNITY_Vite|Vite]]
- [[_COMMUNITY_N8nnode|N8nnode]]
- [[_COMMUNITY_Screens|Screens]]
- [[_COMMUNITY_Favicon|Favicon]]
- [[_COMMUNITY_Icons|Icons]]

## God Nodes (most connected - your core abstractions)
1. `requestJson()` - 43 edges
2. `runAction()` - 7 edges
3. `createProjectFromModal()` - 5 edges
4. `clearCurrentJobId()` - 5 edges
5. `handleComplete()` - 5 edges
6. `handleSave()` - 5 edges
7. `closeMobile()` - 4 edges
8. `createProfile()` - 4 edges
9. `extractUpworkProfile()` - 4 edges
10. `getJobDetail()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `newThread()` --calls--> `clearCurrentJobId()`  [INFERRED]
  frontend\src\components\PhaseLayout.tsx → frontend\src\lib\currentJob.ts
- `deleteThread()` --calls--> `clearCurrentJobId()`  [INFERRED]
  frontend\src\components\PhaseLayout.tsx → frontend\src\lib\currentJob.ts
- `handleSave()` --calls--> `createProfile()`  [INFERRED]
  frontend\src\pages\ProfilePage.tsx → frontend\src\lib\api.ts
- `runAction()` --calls--> `clearCurrentJobId()`  [INFERRED]
  frontend\src\pages\WorkspacePage.tsx → frontend\src\lib\currentJob.ts
- `runAction()` --calls--> `notifyJobsHistoryRefresh()`  [INFERRED]
  frontend\src\pages\WorkspacePage.tsx → frontend\src\lib\events.ts

## Communities

### Community 0 - "Approvejob Beautifymanualprofile"
Cohesion: 0.12
Nodes (32): approveJob(), beautifyManualProfile(), createConnector(), createJobIntake(), deleteConnector(), deleteJob(), deleteProject(), explainJob() (+24 more)

### Community 1 - "Createproject Listprojects"
Cohesion: 0.09
Nodes (9): createProject(), listProjects(), setCurrentJobId(), closeMobile(), createProjectFromModal(), newThread(), refreshProjects(), selectJob() (+1 more)

### Community 2 - "Getjobdetail Listgenerationruns"
Cohesion: 0.13
Nodes (14): getJobDetail(), listGenerationRuns(), notifyJobsHistoryRefresh(), buildDiagramImageCandidates(), driveDownloadUrl(), driveThumbnailUrl(), extractGoogleDriveFileId(), handleIntake() (+6 more)

### Community 3 - "Createprofile Login"
Cohesion: 0.13
Nodes (10): createProfile(), login(), register(), ProtectedRoutes(), handleSubmit(), handleComplete(), trimNull(), hasSessionHint() (+2 more)

### Community 4 - "Handleextract Extractupworkprofile"
Cohesion: 0.25
Nodes (8): extractUpworkProfile(), refreshUpworkProfile(), updateDisplayName(), updateProfile(), handleExtract(), handleExtract(), handleSave(), trimNull()

### Community 5 - "Logout Clearcurrentjobid"
Cohesion: 0.29
Nodes (5): logout(), clearCurrentJobId(), deleteThread(), handleLogout(), clearSessionHint()

### Community 6 - "Listconnectors Startgoogleoauth"
Cohesion: 0.29
Nodes (6): listConnectors(), startGoogleOAuth(), handleGoogleOAuth(), load(), run(), fn()

### Community 7 - "React Eslint"
Cohesion: 0.33
Nodes (4): Expanding the ESLint configuration, React Compiler, React + TypeScript + Vite, The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [th

### Community 8 - "Workflowvisualizer N8nlogo"
Cohesion: 0.67
Nodes (0): 

### Community 9 - "Jobtitles Derivejobtitle"
Cohesion: 1.0
Nodes (2): deriveJobTitle(), firstMeaningfulLine()

### Community 10 - "Jobsdashboardpage Fnum"
Cohesion: 0.67
Nodes (0): 

### Community 11 - "Usagepage Fnum"
Cohesion: 0.67
Nodes (0): 

### Community 12 - "Brandwordmark"
Cohesion: 1.0
Nodes (0): 

### Community 13 - "Apirequesterror Constructor"
Cohesion: 1.0
Nodes (1): ApiRequestError

### Community 14 - "Placeholderpage"
Cohesion: 1.0
Nodes (0): 

### Community 15 - "Postcss"
Cohesion: 1.0
Nodes (0): 

### Community 16 - "Tailwind"
Cohesion: 1.0
Nodes (0): 

### Community 17 - "Vite"
Cohesion: 1.0
Nodes (0): 

### Community 18 - "N8nnode"
Cohesion: 1.0
Nodes (0): 

### Community 19 - "Screens"
Cohesion: 1.0
Nodes (0): 

### Community 20 - "Favicon"
Cohesion: 1.0
Nodes (0): 

### Community 21 - "Icons"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **4 isolated node(s):** `React + TypeScript + Vite`, `React Compiler`, `Expanding the ESLint configuration`, `The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [th`
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Brandwordmark`** (2 nodes): `BrandWordmark()`, `BrandWordmark.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Apirequesterror Constructor`** (2 nodes): `ApiRequestError`, `.constructor()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Placeholderpage`** (2 nodes): `PlaceholderPage.tsx`, `PlaceholderPage()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Postcss`** (1 nodes): `postcss.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tailwind`** (1 nodes): `tailwind.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `N8nnode`** (1 nodes): `N8nNode.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Screens`** (1 nodes): `screens.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Favicon`** (1 nodes): `favicon.svg`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Icons`** (1 nodes): `icons.svg`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `requestJson()` connect `Approvejob Beautifymanualprofile` to `Createproject Listprojects`, `Getjobdetail Listgenerationruns`, `Createprofile Login`, `Handleextract Extractupworkprofile`, `Logout Clearcurrentjobid`, `Listconnectors Startgoogleoauth`?**
  _High betweenness centrality (0.199) - this node is a cross-community bridge._
- **Why does `clearCurrentJobId()` connect `Logout Clearcurrentjobid` to `Createproject Listprojects`, `Getjobdetail Listgenerationruns`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Why does `runAction()` connect `Getjobdetail Listgenerationruns` to `Logout Clearcurrentjobid`, `Listconnectors Startgoogleoauth`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `runAction()` (e.g. with `fn()` and `clearCurrentJobId()`) actually correct?**
  _`runAction()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `clearCurrentJobId()` (e.g. with `newThread()` and `deleteThread()`) actually correct?**
  _`clearCurrentJobId()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `handleComplete()` (e.g. with `createProfile()` and `markProfileHint()`) actually correct?**
  _`handleComplete()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `React + TypeScript + Vite`, `React Compiler`, `Expanding the ESLint configuration` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._