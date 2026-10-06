# 🤖 Enterprise AI Knowledge Assistant

> A secure and scalable backend foundation for an enterprise AI-powered knowledge platform.

The **Enterprise AI Knowledge Assistant** is a backend project designed to provide organizations with a centralized platform for managing enterprise knowledge and building AI-powered question-answering capabilities.

The project is being developed incrementally, starting with a robust **Phase 1 Backend Foundation** using FastAPI, PostgreSQL, SQLAlchemy, Alembic, JWT authentication, and role-based access control.

The architecture is designed to evolve into a complete **Retrieval-Augmented Generation (RAG)** system capable of processing enterprise documents, retrieving relevant information, and generating context-aware responses using Large Language Models.

---

# 🚀 Project Vision

Modern organizations have large amounts of information distributed across:

* 📄 Company documents
* 📚 Policies and guidelines
* 📋 Reports
* 🧑‍💼 HR documents
* 💻 Technical documentation
* 📊 Project information
* 📝 Internal knowledge bases

Finding the right information quickly can be difficult.

The goal of this project is to build an **Enterprise AI Knowledge Assistant** that allows authorized users to interact with organizational knowledge through natural language.

### Long-term workflow

```text
Enterprise Documents
        ↓
Document Processing
        ↓
Text Extraction & Chunking
        ↓
Embeddings
        ↓
Vector Database
        ↓
Semantic Retrieval
        ↓
Relevant Context
        ↓
Large Language Model
        ↓
AI-Generated Answer
        ↓
User
```

Security and authorization will be applied throughout this pipeline so that users only receive information they are allowed to access.

---

# 📌 Current Status

## Phases 0–5 — Foundation, Ingestion & Knowledge (OKF)

The repository now implements **Phases 0–5 of the build plan** (see
[build_plan.md](build_plan.md) and the audit in [docs/AUDIT_0-5.md](docs/AUDIT_0-5.md)).

### Implemented

* ✅ FastAPI project scaffold
* ✅ PostgreSQL-ready SQLAlchemy setup
* ✅ Alembic migration support
* ✅ JWT authentication APIs (HS256, role re-read per request, active-user revocation)
* ✅ Role-based access + ACL: document **visibility** (`all` / `department`) and per-chunk / per-fact ACL denormalization
* ✅ Base route groups for:

  * Users
  * Authentication
  * Documents
  * Knowledge
  * Departments
  * Chat
* ✅ Document ingestion: upload, magic-byte validation, SHA-256 (duplicate 409 + `?force`), `413`/`415`/`422`, async-style lifecycle (`uploaded → processing → ready/failed`) with a status endpoint
* ✅ Text extraction for **PDF, DOCX, PPTX, TXT, MD** (unicode-safe cleaner, DOCX headings/lists/tables, PPTX numeric slide order + speaker notes, header/footer removal at the >40% threshold)
* ✅ Token-aware chunking (section-based default, contiguous indices, `token_count`, ACL copied onto chunks)
* ✅ OKF knowledge objects: typed schema with required attributes, closed relation predicates, versioning, admin **review workflow** (`pending_review → approved/rejected`), bulk review, archive-on-delete
* ✅ Audit log (`audit_logs`) for auth, document and knowledge events
* ✅ Liveness `/health` and readiness `/health/ready` (503 when the DB is down)
* ✅ CORS, `X-Request-ID` request tracing, structured logging
* ✅ Application logging, centralized error handling
* ✅ Swagger / OpenAPI documentation (`docs/openapi.json`)
* ✅ Automated tests (44 passing incl. one regression test per P0/P1 audit fix)

The current phase focuses on creating a clean and scalable backend architecture that can support the future AI/RAG components.

---

# 🏗️ Architecture

The current Phase 1 architecture can be represented as:

```text
                    ┌─────────────────────┐
                    │       Client        │
                    │ Web / Mobile / API  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │      REST API       │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌───────────┐    ┌───────────┐    ┌───────────┐
        │   Auth    │    │   Users   │    │   RBAC    │
        └───────────┘    └───────────┘    └───────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌───────────┐    ┌───────────┐    ┌───────────┐
        │ Documents │    │ Knowledge │    │   Chat    │
        └───────────┘    └───────────┘    └───────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    SQLAlchemy       │
                    │        ORM          │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     PostgreSQL      │
                    └─────────────────────┘
```

---

# 🧩 Technology Stack

| Technology               | Purpose                      |
| ------------------------ | ---------------------------- |
| 🐍 **Python**            | Backend programming          |
| ⚡ **FastAPI**            | REST API framework           |
| 🐘 **PostgreSQL**        | Relational database          |
| 🗃️ **SQLAlchemy**       | ORM and database interaction |
| 🔄 **Alembic**           | Database migrations          |
| 🔐 **JWT**               | Authentication               |
| 🧪 **Pytest**            | Automated testing            |
| 📖 **Swagger / OpenAPI** | API documentation            |

---

# 📁 Project Structure

```text
Enterprise-AI-Knowledge-Assistant/
│
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── auth/
│   │       ├── users/
│   │       ├── documents/
│   │       ├── knowledge/
│   │       └── chat/
│   │
│   ├── core/
│   │   ├── configuration
│   │   ├── security
│   │   └── logging
│   │
│   ├── db/
│   │   ├── database
│   │   └── models
│   │
│   └── main.py
│
├── alembic/
│   └── migrations
│
├── storage/
│
├── test_uploads/
│
├── tests/
│
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

> The exact internal module structure may evolve as additional phases of the project are implemented.

---

# 🔐 Authentication & Authorization

Security is one of the core architectural components of the project.

The Phase 1 backend provides the foundation for:

### JWT Authentication

The application uses JSON Web Tokens for authenticated API access.

```text
User
 ↓
Login
 ↓
Credentials Verification
 ↓
JWT Token
 ↓
Authenticated API Requests
```

### Role-Based Access Control

The project includes the foundation for role-based authorization.

Future roles may include:

```text
ADMIN
MANAGER
EMPLOYEE
KNOWLEDGE_MANAGER
```

This will allow the system to control access to enterprise documents, knowledge bases, and AI functionality.

---

# 📄 Document Management

A dedicated document route group is included in the Phase 1 backend.

The document management layer is intended to evolve into a complete enterprise document-processing pipeline.

Future support can include:

* PDF
* DOCX
* PPTX
* XLSX
* TXT
* Markdown
* Other enterprise document formats

Planned processing:

```text
Document Upload
      ↓
Validation
      ↓
Text Extraction
      ↓
Chunking
      ↓
Metadata Extraction
      ↓
Embedding Generation
      ↓
Vector Storage
```

---

# 🧠 Knowledge Management

The project contains a dedicated **Knowledge** route group that will become the foundation for the enterprise knowledge layer.

The planned knowledge system will support:

* Knowledge bases
* Document indexing
* Semantic search
* Metadata filtering
* Vector search
* Retrieval
* Source references

---

# 💬 AI Chat

A dedicated **Chat** route group is included in the backend architecture.

The long-term goal is to provide an AI assistant capable of answering questions using authorized enterprise knowledge.

Planned flow:

```text
User Question
      ↓
Authentication
      ↓
Authorization / RBAC
      ↓
Query Processing
      ↓
Knowledge Retrieval
      ↓
Relevant Documents
      ↓
LLM
      ↓
Grounded Response
```

---

# 🔍 Planned RAG Pipeline

One of the major future components of the project is a **Retrieval-Augmented Generation (RAG)** pipeline.

The planned architecture is:

```text
                USER
                  │
                  ▼
             ┌─────────┐
             │ FastAPI │
             └────┬────┘
                  │
          Authentication
                  │
             Authorization
                  │
                  ▼
             ┌─────────┐
             │  Chat   │
             └────┬────┘
                  │
                  ▼
          Query Processing
                  │
                  ▼
             Retriever
                  │
                  ▼
            Vector DB
                  │
                  ▼
          Relevant Context
                  │
                  ▼
               LLM
                  │
                  ▼
          Grounded Answer
```

Potential technologies for future phases include:

* Embedding models
* Vector databases
* Semantic search
* Hybrid search
* Reranking
* LLM providers
* RAG frameworks

---

# 🛡️ Security Roadmap

Enterprise AI systems require additional security beyond normal authentication.

Future security capabilities may include:

* 🔐 Fine-grained permissions
* 📄 Document-level access control
* 🏢 Department-level isolation
* 📋 Audit logging
* 🕵️ PII detection
* 🛡️ Prompt-injection detection
* 🚦 Rate limiting
* 🤖 AI governance
* 🔎 Response/source validation

---

# ⚙️ Setup

## 1. Clone the Repository

```powershell
git clone https://github.com/pankajkumar8709/Enterprise-AI-Knowledge-Assistant.git
```

Move into the project directory:

```powershell
cd Enterprise-AI-Knowledge-Assistant
```

---

## 2. Create a Virtual Environment

```powershell
python -m venv .venv
```

Activate the environment:

```powershell
.venv\Scripts\Activate.ps1
```

---

## 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Copy the example environment file:

```powershell
copy .env.example .env
```

Then update the `.env` file.

Configure:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/enterprise_ai
```

Replace the values with your PostgreSQL configuration.

> ⚠️ Never commit `.env` or database credentials, JWT secrets, API keys, or other sensitive information to GitHub.

---

# 🗄️ Database Setup

The application uses PostgreSQL with SQLAlchemy.

After configuring your database, run the Alembic migrations:

```powershell
alembic upgrade head
```

This applies the current database schema.

---

# ▶️ Run the Application

Start the FastAPI development server:

```powershell
uvicorn app.main:app --reload
```

The application will start at:

```text
http://127.0.0.1:8000
```

---

# 📖 API Documentation

FastAPI automatically generates interactive API documentation.

### Swagger UI

Open:

```text
http://127.0.0.1:8000/docs
```

### ReDoc

Open:

```text
http://127.0.0.1:8000/redoc
```

Swagger can be used to explore and test the available API endpoints.

---

# 🧪 Testing

Run the test suite:

```powershell
pytest
```

For verbose output:

```powershell
pytest -v
```

Testing will be expanded as new modules and AI capabilities are added.

---

# 🩺 Health Check

The application includes health-check functionality to verify that the backend is running correctly.

This can later be extended to monitor:

* API availability
* PostgreSQL connectivity
* Vector database availability
* LLM provider availability
* Background processing services

---

# 📊 Development Roadmap

## Phase 1 — Backend Foundation

* [x] FastAPI project scaffold
* [x] PostgreSQL-ready SQLAlchemy setup
* [x] Alembic migration support
* [x] JWT authentication APIs
* [x] Role-based access foundation
* [x] Users route group
* [x] Authentication route group
* [x] Documents route group
* [x] Knowledge route group
* [x] Chat route group
* [x] Logging
* [x] Error handling
* [x] Health checks
* [x] Swagger documentation
* [x] Automated testing

---

## Phase 2 — Document Intelligence

* [x] Document upload
* [x] File validation
* [x] PDF processing
* [x] DOCX processing
* [x] PPTX processing
* [ ] XLSX processing
* [x] Text extraction
* [x] Document chunking
* [x] Metadata extraction
* [ ] Document versioning

---

## Phase 3 — Knowledge & RAG

* [ ] Embedding generation
* [ ] Vector database
* [ ] Document indexing
* [ ] Semantic search
* [ ] Hybrid search
* [ ] Metadata filtering
* [ ] Reranking
* [ ] Context retrieval
* [ ] Source citations

---

## Phase 4 — LLM Integration

* [ ] LLM provider integration
* [ ] Model abstraction
* [ ] Prompt management
* [ ] Context-aware generation
* [ ] Streaming responses
* [ ] Conversation history
* [ ] Response validation

---

## Phase 5 — Enterprise Security

* [x] Fine-grained RBAC (admin/employee + per-object review workflow)
* [x] Document-level permissions (`visibility`: `all` / `department`)
* [x] Department-level access (department ACL on documents, chunks and knowledge objects)
* [x] Audit logs
* [ ] PII detection
* [ ] Prompt-injection protection
* [ ] Rate limiting
* [ ] AI governance

---

## Phase 6 — Frontend & Analytics

* [ ] Enterprise AI chat UI
* [ ] Admin dashboard
* [ ] User management
* [ ] Document management UI
* [ ] Knowledge-base management
* [ ] Usage analytics
* [ ] AI interaction analytics

---

# 💡 Potential Use Cases

### 🏢 Human Resources

> "What is the company's leave policy?"

### 💻 IT Support

> "How do I troubleshoot the production deployment issue?"

### 📋 Project Management

> "What are the current project risks?"

### ⚖️ Compliance

> "What requirements are defined in the compliance policy?"

### 🎓 Employee Onboarding

> "What documents should a new employee read?"

### 🔧 Engineering

> "What is the standard procedure for deploying a service?"

The future RAG layer will allow these answers to be grounded in authorized enterprise documents.

---

# 🎯 Project Objectives

The main objectives are to build a system that is:

### 🔐 Secure

Protect enterprise information through authentication and authorization.

### 📈 Scalable

Use a modular backend architecture that can grow as new services are introduced.

### 🧠 Intelligent

Integrate RAG and LLM technologies for natural-language knowledge access.

### 📚 Knowledge-Centric

Transform enterprise documents into a searchable and useful knowledge base.

### 🏢 Enterprise-Ready

Provide the foundations required for organizations to manage users, permissions, documents, knowledge, and AI interactions.

---

# 🔄 Overall System Vision

```text
                  ENTERPRISE AI KNOWLEDGE ASSISTANT

                         ┌───────────────┐
                         │     Users     │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │    FastAPI    │
                         └───────┬───────┘
                                 │
                ┌────────────────┼────────────────┐
                │                │                │
                ▼                ▼                ▼
             Auth/RBAC       Documents        Knowledge
                │                │                │
                └────────────────┼────────────────┘
                                 │
                                 ▼
                           RAG Pipeline
                                 │
                   ┌─────────────┼─────────────┐
                   │             │             │
                   ▼             ▼             ▼
               Embeddings    Vector DB       LLM
                   │             │             │
                   └─────────────┼─────────────┘
                                 │
                                 ▼
                         Grounded Response
                                 │
                                 ▼
                              User
```

---

# 🤝 Contributing

Contributions are welcome.

### 1. Fork the repository

### 2. Create a feature branch

```powershell
git checkout -b feature/new-feature
```

### 3. Make your changes

### 4. Run tests

```powershell
pytest
```

### 5. Commit your changes

```powershell
git commit -m "Add new feature"
```

### 6. Push your branch

```powershell
git push origin feature/new-feature
```

### 7. Create a Pull Request

---

# 👨‍💻 Author

## Pankaj Kumar Mahto

Computer Science & Engineering Student

Interested in:

* Backend Development
* Artificial Intelligence
* Machine Learning
* RAG Systems
* Enterprise AI
* Secure AI Applications

### GitHub

https://github.com/pankajkumar8709

---

# ⭐ Support

If you find this project useful, consider giving the repository a ⭐ on GitHub.

Contributions, suggestions, and feedback are welcome.

---

## 🚀 Enterprise AI Knowledge Assistant

**Building a secure foundation for intelligent enterprise knowledge.**
