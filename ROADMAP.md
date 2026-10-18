# 6-Week Build Plan (Oct 6 – Nov 16, 2026), 30–60 min/day

The code runs and is tested. Your job each day is to **run it, read it, change one thing, and
be able to explain it out loud**. Interviewers will ask "why did you do it this way?" — the
"Design decisions" section of each README is your study guide.

> **Apply by Sunday Oct 18, not Nov 16.** Bell extends offers on a rolling basis from September,
> so seats fill before the deadline. Apply once Project 1 is public and live; keep building after.

> **Day 1 also:** ask Bell's campus recruiting team whether your pre-master's experience counts
> toward the "less than 3 years" rule. Better to know now.

---

## Week 1 (Oct 6–11): Git, SQL and the pipeline — *Project 1 local*

| Day | Do this | You can now say |
|---|---|---|
| Tue | Install Git + VS Code. Create a public GitHub repo `bell-churn-platform`, push this folder (`git init`, `add`, `commit`, `push`). | Version control with Git/GitHub |
| Wed | `pip install -e ".[dev]"`, run `python -m churn.etl`. Read `etl.py` top to bottom. Break the CSV on purpose (duplicate a row) and watch validation catch it. | ETL with data-quality checks |
| Thu | Run `python -m churn.etl --query sql/analysis.sql`. Read `schema.sql`. Write **two queries of your own** (churn by payment method; churn for senior citizens) and add them to `analysis.sql`. Commit. | SQL, joins, aggregation, data modeling |
| Fri | Install Docker Desktop. `docker compose up --build`. Open `localhost:8000/docs`. Same pipeline, now on PostgreSQL. | Docker, PostgreSQL |
| Sat | Run `python -m churn.train`. Learn ROC-AUC, PR-AUC and lift well enough to explain each in one sentence. Why did logistic regression win? | Predictive modeling, model selection |
| Sun | Run `pytest -q`. Read `test_api.py`. Make one test fail on purpose, then fix it. | Testing |

## Week 2 (Oct 12–18): CI/CD, cloud, Agile — *Project 1 live, then APPLY*

| Day | Do this | You can now say |
|---|---|---|
| Mon | Push to GitHub and open the **Actions** tab: CI runs lint, tests, Postgres ETL, Docker build. Fix anything red. | CI/CD with GitHub Actions |
| Tue | Create a free Jira Software site. Make an epic per component (ETL, Model, API, Agent, Deploy), stories for what you did, run it as a 1-week sprint. | Jira, Agile/Scrum |
| Wed | Follow `deploy/gcp-setup.md` steps 0–3 (budget alert first!). | Google Cloud, IAM, least privilege |
| Thu | Steps 4–5, then run the deploy workflow. Open your live `/docs` URL on your phone. | Cloud Run, Workload Identity, deployment |
| Fri | Call `/predict` 30+ times, then read `/monitoring/drift`. Explain PSI in one sentence. | Model monitoring, drift |
| Sat | Update the resume (see "Resume lines" below). Add GitHub + live URL to the header. | — |
| **Sun** | **Apply to Bell.** Upload resume + transcripts. | — |

## Week 3 (Oct 19–25): GenAI agent + interview prep

| Day | Do this | You can now say |
|---|---|---|
| Mon | Get an Anthropic API key, set a $5 spending limit, run `python -m churn.agent "…"` with 3 questions. | LLM applications |
| Tue | Read `agent.py`. Write down the 4 guardrail layers. Add a test that blocks one more dangerous query. | Prompt engineering, AI safety guardrails |
| Wed | Edit `SYSTEM_PROMPT` to improve one bad answer you saw. Before/after in a commit message. | Prompt iteration |
| Thu | Draw the architecture in Miro (free) from the README diagram. Add the image to the README. | Systems design, Miro |
| Fri–Sun | Video-interview practice: record 90-second answers to "walk me through a project", "a time you led", "a technical trade-off you made". | — |

## Week 4 (Oct 26–Nov 1): Project 2 — EMG, local

| Day | Do this |
|---|---|
| Mon | Push `emg-gesture-service` to its own public repo. Watch CI (it downloads the real data and trains). |
| Tue | Locally: `python -m emg.data download`, `python -m emg.train`. Fill in the README results table. |
| Wed | Compare within- vs cross-subject accuracy. Write 3 sentences linking the gap to your thesis Aim 2. |
| Thu | Try 150 ms and 250 ms windows (`window_ms`). Record the effect. |
| Fri–Sun | Read `features.py` until you can derive each Hudgins feature on a whiteboard. |

## Week 5 (Nov 2–8): Project 2 on AWS

| Day | Do this |
|---|---|
| Mon | AWS account + zero-spend budget. `deploy/aws-setup.md` steps 1–3. |
| Tue | Step 4 (OIDC + least-privilege policy). Read every line of the policy. |
| Wed | Step 5, run the deploy workflow, test `/docs` on the Function URL. |
| Thu–Sun | Buffer for anything that broke. Debugging cloud IAM *is* the skill. |

## Week 6 (Nov 9–16): Polish

- Pin both repos on your GitHub profile; write a profile README.
- One LinkedIn post per project (what, results, one lesson).
- Optional stretch: load the churn warehouse into BigQuery and run `analysis.sql` there.
- Re-read both "Design decisions" sections the night before any interview.

---

## Resume lines (add each only after you've done that week's work)

**After Week 2**, add a Projects entry:

> **Telecom Churn Prediction Platform** | Python, SQL, PostgreSQL, scikit-learn, FastAPI, Docker, GitHub Actions, Google Cloud Run
> - Built an end-to-end churn system on 7,043 telecom customers: validated ETL into a normalized SQL warehouse, CV-selected model (ROC-AUC 0.84, 2.85× top-decile lift), and a FastAPI scoring service deployed to Cloud Run.
> - Automated CI/CD with GitHub Actions (lint, 23 tests, model-quality gate, PostgreSQL ETL check, Docker smoke test) and keyless Workload Identity deployment.
> - Added MLOps monitoring: logged every prediction and computed PSI drift against training distributions.

**After Week 3**, add:

> - Built an LLM analytics agent that turns business questions into SQL behind layered guardrails (SELECT-only validation, read-only transactions, row caps, self-correction), tested with a mock LLM in CI.

**After Week 5**, add a second entry:

> **EMG Gesture Recognition Service** | Python, scikit-learn, FastAPI, Docker, AWS Lambda, ECR
> - Classified 6 hand gestures from 8-channel sEMG (36 subjects) with Hudgins features; compared LDA and Random Forest under within- vs cross-subject validation (fill in your real numbers).
> - Deployed as a serverless container API on AWS Lambda via GitHub OIDC and least-privilege IAM.

Skills to add only once earned: SQL, PostgreSQL, Docker, GitHub Actions (CI/CD), Google Cloud
(Cloud Run), AWS (Lambda, ECR, IAM), FastAPI, Jira, Agile/Scrum, Miro, LLM applications.
