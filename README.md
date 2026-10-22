# Planora — Missed Task Replanner

**A smarter way to recover from missed tasks, rebuild your schedule, and stay productive without the guilt.**

Planora is a full-stack productivity application designed to help users recover when they fall behind on their plans. Instead of simply tracking tasks, Planora focuses on intelligent replanning, deadline protection, workload management, and sustainable productivity.

## ✨ Key Features

- **Intelligent Task Replanning** — Reorganize incomplete and overdue tasks into a more manageable schedule.
- **Overload Detection** — Identify when your workload becomes difficult to manage.
- **Smart Recommendations** — Get guidance on what to work on next.
- **Energy-Based Planning** — Plan tasks around your available energy.
- **Bad Day Mode** — Recover from an unproductive day without starting over.
- **Task History** — Track schedule changes and understand why tasks were rescheduled.
- **Weekly Reflection** — Review progress, recover missed tasks, and reflect on planning accuracy.
- **Gentle Progress Tracking** — Encourage consistency without relying on punishing streaks.

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | React.js, Vite |
| Backend | Python, FastAPI |
| ORM & Validation | SQLAlchemy, Pydantic |
| Database | PostgreSQL |
| Testing | Pytest |
| Deployment | Vercel, Railway |


## 🏗️ Architecture

```text
User
  │
  ▼
React + Vite Frontend
  │
  ▼
FastAPI Backend
  │
  ├── Task Management
  │
  ├── Planning Engine
  │     ├── Schedule Generation
  │     ├── Missed-Task Recovery
  │     └── Task Recommendations
  │
  ├── History & Reflection
  │
  ▼
SQLAlchemy
  │
  ▼
PostgreSQL Database
```

## 🚀 Getting Started

### Prerequisites

- Node.js and npm
- Python 3.11+
- A configured database, if required by your current setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <YOUR_REPOSITORY_NAME>
```

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Start the backend

Open a separate terminal:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

**Windows:**

```bash
.venv\Scripts\activate
```

Install the dependencies and start the server:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The FastAPI interactive API documentation is generally available at:

`http://127.0.0.1:8000/docs`

### 4. Configure environment variables

Create the required environment files for your local setup. Configure database credentials, API URLs, and other secrets as needed. Never commit passwords, API keys, or production credentials.

## 🎯 Project Goal

Planora is built around one simple idea:

**Missing a task shouldn't mean losing control of your entire schedule.**

By prioritizing recovery over perfection, Planora aims to make productivity more realistic, flexible, and sustainable.

## 👩‍💻 Built With

Developed as a full-stack software project focused on practical scheduling problems, intelligent planning, and user-centered productivity.
