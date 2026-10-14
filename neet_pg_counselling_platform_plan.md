# NEET PG Counselling Intelligence Platform

## 1. Product Vision

Build a web application that helps NEET PG aspirants understand historical admission possibilities, compare college and branch options, and prepare a data-informed counselling shortlist.

The platform will begin with two connected modules:

- **College Predictor:** Finds and classifies historical college-course options based on a candidate's profile.
- **Counselling Assistant:** Explains predictor results and answers counselling questions using structured allotment data and verified guidance.

The platform should provide transparent, evidence-based estimates—not guarantees of admission. Historical cutoffs, seat availability, eligibility rules, and counselling outcomes can change.

## 2. Module A — NEET PG College Predictor

### Candidate Inputs

- All India Rank (AIR)
- Reservation category
- Counselling quota
- Preferred branches
- Preferred states or regions
- Institution preferences, such as government colleges
- Course preferences, such as MD/MS
- Counselling rounds to consider

Support for each category, quota, and filter will depend on the availability and validation of the underlying data.

### Recommendation Output

Return matching historical college-course options, organized into configurable classifications:

- **Safe:** Historical closing rank provides a substantial margin.
- **Good chance:** Historical data suggests a favorable possibility.
- **Borderline:** Candidate rank is near the historical closing-rank boundary.
- **Later-round opportunity:** The option appeared within a relevant later-round closing-rank range.
- **Reach:** The candidate's rank is less competitive than the historical closing rank, but the option may be worth considering.

These are historical estimates, not guaranteed outcomes or statistically validated admission probabilities.

### Results Dashboard

- Summary counts by round and classification
- Searchable and filterable college-course results
- Filters for branch, state, college, round, and classification
- Historical opening and closing ranks
- Relevant quota and seat category
- Round-wise cutoff changes and allotment information
- Explanation of why each option matches the candidate's profile
- Save and export functionality

The application must distinguish a personal shortlist from an official counselling choice list. Export compatibility with official portals must not be implied unless verified.

## 3. Module B — Counselling Assistant

### Purpose

Provide a context-aware assistant that explains predictor results, answers questions about historical allotment data, and helps candidates understand their options.

### Core Capabilities

1. **Data questions:** Retrieve facts such as historical closing ranks, branches, colleges, categories, and counselling rounds.
2. **Recommendation questions:** Query the predictor and explain which options match the candidate's preferences.
3. **General counselling questions:** Explain counselling concepts using verified guidance and current official sources where needed.

### Evidence-Based Answers

The assistant should use the candidate's current profile and relevant database records. Explanations should identify the supporting college, course, rank, round, category, and data year when available.

For current counselling rules, eligibility, and seat matrices, use current official sources rather than relying only on historical data. If evidence is missing or insufficient, the assistant should say so.

### Implementation Approach

- Use an LLM for natural-language understanding and explanations.
- Retrieve facts through backend API endpoints and controlled database-query functions.
- Ground answers in structured records rather than allowing the model to invent ranks, colleges, seat availability, or admission probabilities.
- Test the assistant with questions whose answers are known.

## 4. Technical Architecture

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | Next.js + TypeScript | User interface and interactive dashboard |
| Styling | Tailwind CSS | Layout and design |
| Backend | FastAPI | Predictor logic and assistant endpoints |
| Database | PostgreSQL | Historical allotments, colleges, courses, and cutoffs |
| Data processing | Python + Pandas | PDF parsing, cleaning, and validation |
| Request validation | Pydantic | Validate API inputs and outputs |
| Charts | Apache ECharts or Recharts | Cutoff and historical trend visualizations |
| Deployment | Vercel + Render, or equivalent | Frontend and backend hosting |

### Data Flow

```text
Official MCC Allotment PDFs
          |
          v
 Python Data Pipeline
          |
          v
Validation and Normalization
          |
          v
     PostgreSQL
          |
          v
       FastAPI
          |
          +----------------------+
          |                      |
          v                      v
  College Predictor      Counselling Assistant
          |                      |
          +----------+-----------+
                     |
                     v
               Next.js UI
```

The existing Jupyter notebook should be reused as the foundation of the data-processing workflow where appropriate. The web application should query prepared database tables rather than rerunning the entire notebook for every request.

Suggested initial API endpoints:

```text
POST /api/predict
GET  /api/colleges
GET  /api/colleges/{college_id}
GET  /api/cutoffs
GET  /api/branches
GET  /api/states
```

Finalize endpoint contracts after inspecting the actual data schemas.

## 5. Development Roadmap

### Milestone 1 — Data Foundation

- Inspect existing notebooks, CSV files, and Excel outputs.
- Identify available fields: candidate category, seat category, quota, round, course, college, rank, and reporting status.
- Define consistent identifiers for colleges and courses across rounds.
- Validate duplicate records, labels, and cutoff calculations.
- Design the database schema and a repeatable import pipeline.

### Milestone 2 — Predictor API

- Implement candidate-profile input validation.
- Query matching historical options.
- Calculate configurable historical classifications.
- Return cutoff details, round information, and supporting data.
- Test API responses against the existing notebook outputs.

### Milestone 3 — Frontend

- Build the candidate profile form.
- Create the results dashboard and filters.
- Add college and course detail pages.
- Display round-wise cutoff comparisons and explanation of classifications.
- Ensure historical estimates and limitations are clearly communicated.

### Milestone 4 — Counselling Assistant

- Connect the LLM to predictor APIs and controlled database-backed functions.
- Support data questions, recommendation explanations, and general counselling questions.
- Use current official sources for current rules and eligibility.
- Test factual accuracy, use of candidate context, source grounding, and handling of missing evidence.

### Milestone 5 — Shortlists and Export

- Allow candidates to save and organize shortlisted options.
- Support preference reordering.
- Export the shortlist for further review.
- Clearly distinguish the application's shortlist from an official counselling submission.

### Milestone 6 — Expansion

- Add more historical counselling years as official data becomes available.
- Improve college and course metadata.
- Add richer historical analysis and recommendation methods.
- Introduce further features—such as college comparisons, counselling simulations, and seat-movement analysis—after the core predictor and assistant are reliable.

## Guiding Principles

- Treat historical cutoffs as evidence, not guarantees.
- Do not present admission probabilities unless supported by a validated statistical model.
- Keep recommendations aligned with the candidate's stated preferences.
- Make the source year and limitations visible.
- Use current official sources for current counselling rules and seat information.
- Build the predictor first, then connect the assistant to the same validated data.
