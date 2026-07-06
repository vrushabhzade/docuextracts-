# DocuExtract — Structured Data Extraction Pipeline for Indian Documents

DocuExtract is a portfolio-grade, AWS-native web application that extracts clean, structured JSON from photos of Indian documents — ration cards, exam admit cards, handwritten forms — even when the documents are skewed, low-quality, or contain a mix of English, Hindi, and Marathi text. Every extracted record is automatically indexed into a local knowledge graph so you can ask natural-language questions across the whole history of processed documents.

---

## Highlights

- **Multilingual OCR** — Tesseract LSTM engine with English, Hindi, and Marathi language packs.
- **OpenCV preprocessing** — deskew, denoise, binarize, and contrast enhancement before OCR.
- **Schema-guided extraction** — Google Gemini 2.0 Flash returns strictly typed JSON tailored per document type.
- **Rule-based validation** — Verhoeff checksum for ration card numbers, format checks for roll numbers and dates, plus a confidence badge (high / medium / low) per field.
- **Semantic knowledge graph** — [Cognee](https://github.com/topoteretes/cognee) ingests every extraction in the background and powers natural-language search across the full record history.
- **Human-in-the-loop corrections** — Editable field cards with bounding-box highlights overlaid on the original image.
- **Cloud-agnostic storage & database layers** — Supports AWS (S3 + DynamoDB single-table design) and GCP (Google Cloud Storage + BigQuery) with automatic local filesystem/SQLite mock fallbacks.

---

## Architecture Diagram

```text
                   +----------------------------------+
                   |       Amplify Web Hosting        |
                   |      (React 18 + Vite UI)        |
                   +----------------+-----------------+
                                    |
                                    | HTTP Requests (CORS)
                                    v
                   +----------------+-----------------+
                   |           ECS Fargate            |
                   |      (FastAPI App Container)     |
                   |                                  |
                   |   +--------------------------+   |
                   |   |    OpenCV Preprocess     |   |
                   |   +--------------+-----------+   |
                   |                  |               |
                   |   +--------------v-----------+   |
                   |   |    Tesseract Multilingual|   |
                   |   |    OCR (eng+hin+mar)     |   |
                   |   +--------------+-----------+   |
                   |                  |               |
                   |   +--------------v-----------+   |
                   |   |    Gemini 2.0 Flash      |   |
                   |   |    Structured Output     |   |
                   |   +--------------+-----------+   |
                   |                  |               |
                   |   +--------------v-----------+   |
                   |   |    Verhoeff & Field      |   |
                   |   |    Rule Validator        |   |
                   |   +--------------+-----------+   |
                   |                  |               |
                   |   +--------------v-----------+   |
                   |   |   Cognee Knowledge Graph |   |
                   |   |   (Background Ingestion) |   |
                   |   +--------------+-----------+   |
                   +--------+--------+--------+-------+
                            |        |        |
         Fetch API Key      |        |        | Upload Originals/Previews
  +-------------------------+        |        +------------------------+
  |                                  |                                 |
  v                                  v Save Records                    v
+------------------+     +-----------+------------+      +-------------+
| Secrets Manager  |     |   DynamoDB Single Table|      |   S3 Bucket |
| (api-key secret) |     |  "docuextract-records" |      | (Private)   |
+------------------+     +------------------------+      +-------------+
```

---

## Tech Stack

| Layer            | Technology                                                        |
|------------------|-------------------------------------------------------------------|
| Frontend         | React 18, Vite, Tailwind CSS, Lucide icons, Axios                 |
| Backend          | FastAPI, Uvicorn, Pydantic v2, Pydantic Settings                  |
| OCR              | Tesseract 5 (eng + hin + mar traineddata)                         |
| Image processing | OpenCV (headless), NumPy                                          |
| Extraction LLM   | Google Gemini 2.0 Flash (JSON-mode), or local Ollama              |
| Knowledge graph  | Cognee + FastEmbed (BAAI/bge-small-en-v1.5)                       |
| Storage          | AWS S3 (images), AWS DynamoDB (records + corrections) or GCP GCS + BigQuery |
| Hosting          | AWS ECS Fargate (backend), AWS Amplify / Vercel (frontend)        |

---

## Repository Layout

```text
Docuextracts/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entrypoint + routes
│   │   ├── config.py               # Pydantic settings (.env loader)
│   │   ├── models.py               # Request / response models
│   │   ├── preprocessing.py        # OpenCV pipeline
│   │   ├── ocr.py                  # Tesseract wrapper
│   │   ├── extraction.py           # Gemini / Ollama extraction
│   │   ├── validation.py           # Verhoeff + format checks
│   │   ├── cognee_integration.py   # Knowledge-graph ingestion & search
│   │   ├── storage.py              # Cloud-agnostic storage router
│   │   ├── database.py             # Cloud-agnostic database router
│   │   ├── schemas/                # Per-document-type field schemas
│   │   ├── aws/                    # S3 + DynamoDB + Secrets clients
│   │   └── gcp/                    # Google Cloud Storage + BigQuery clients & mocks
│   ├── tests/                      # pytest suite (moto- and mock-backed)
│   ├── Dockerfile                  # Tesseract + OpenCV + Python image
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 # Main UI + semantic search panel
│   │   ├── api/client.js           # Axios client (env / localStorage override)
│   │   └── components/             # UploadCapture, ProcessingStages, ExtractedFieldsEditor
│   ├── vercel.json
│   └── package.json
├── sample_documents/
│   ├── ration_card_sample.png      # Example input image
│   └── README.md
└── README.md
```

---

## Local Setup & Run

### 1. System Dependencies (Tesseract OCR)
The pipeline requires Tesseract OCR with English, Hindi, and Marathi language packs.

#### Debian / Ubuntu
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-hin tesseract-ocr-mar
```

#### macOS (Homebrew)
```bash
brew install tesseract
brew install tesseract-lang
```

#### Windows
1. Download the installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki).
2. During installation, tick **Additional script data → Devanagari** and **Additional language data → Hindi, Marathi**.
3. Add the Tesseract folder (e.g. `C:\Program Files\Tesseract-OCR`) to your system **Path**.

### 2. Backend
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # then fill in GEMINI_API_KEY + AWS creds
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the test suite:
```bash
python -m pytest tests/
```

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
The web UI will be available at `http://localhost:5173`.

---

## Environment Variables

### Backend (`backend/.env`)
| Variable                  | Required | Default                     | Description                                              |
|---------------------------|----------|-----------------------------|----------------------------------------------------------|
| `ENVIRONMENT`             | No       | `local`                     | `local` re-reads `.env` on every access; `production` caches the settings object. |
| `ALLOWED_ORIGIN`          | No       | `http://localhost:5173`     | Extra CORS origin (Vite dev URL is always allowed).      |
| `GEMINI_API_KEY`          | Yes (Gemini) | —                       | API key from Google AI Studio.                           |
| `GEMINI_MODEL`            | No       | `gemini-2.0-flash`          | Gemini model id.                                        |
| `DOCUEXTRACT_LLM_PROVIDER`| No       | `gemini`                    | `gemini` or `ollama`.                                    |
| `OLLAMA_API_URL`          | If Ollama | `http://localhost:11434`   | Base URL of the local Ollama server.                     |
| `OLLAMA_MODEL`            | If Ollama | `llama3`                   | Model name served by Ollama.                             |
| `AWS_REGION`              | Yes      | `us-east-1`                 | AWS region for S3 + DynamoDB.                            |
| `AWS_ACCESS_KEY_ID`       | Yes (non-IAM) | —                      | Local / CI credentials.                                 |
| `AWS_SECRET_ACCESS_KEY`   | Yes (non-IAM) | —                      | Local / CI credentials.                                 |
| `DYNAMODB_TABLE`          | No       | `docuextract-records`       | DynamoDB table name.                                     |
| `S3_BUCKET`               | No       | `docuextract-images-bucket-name` | S3 bucket for original + preprocessed images.       |
| `AWS_ENDPOINT_URL`        | No       | —                           | Override for LocalStack / custom endpoints.              |
| `DYNAMODB_ENDPOINT_URL`   | No       | —                           | Override for local DynamoDB.                             |
| `STORAGE_PROVIDER`        | No       | `aws`                       | Active storage provider: `aws` or `gcp`.                  |
| `DATABASE_PROVIDER`       | No       | `aws`                       | Active database provider: `aws` or `gcp`.                 |
| `GCP_PROJECT`             | If GCP   | —                           | Google Cloud Project ID.                                 |
| `GCS_BUCKET`              | If GCP   | `docuextract-files`         | Google Cloud Storage bucket for document images.          |
| `BIGQUERY_DATASET`        | If GCP   | `docuextract_dataset`       | BigQuery dataset name.                                   |
| `BIGQUERY_TABLE`          | If GCP   | `docuextract_records`       | BigQuery table name.                                     |
| `GCP_CREDENTIALS_JSON`    | No       | —                           | Local path to GCP service account credentials file, or raw JSON string content. |

### Frontend (`frontend/.env.local`)
| Variable             | Default                    | Description                                                |
|----------------------|----------------------------|------------------------------------------------------------|
| `VITE_API_BASE_URL`  | `http://127.0.0.1:8000`    | Backend URL. Can be overridden at runtime via `localStorage.setItem('docuextract_api_url', '...')`. |

---

## API Endpoints

| Method | Path                  | Purpose                                                         |
|--------|-----------------------|-----------------------------------------------------------------|
| GET    | `/health`             | Liveness probe.                                                 |
| POST   | `/api/extract`        | Upload a document image; runs the full pipeline.                |
| POST   | `/api/extract/correct`| Persist human corrections for a previous extraction.            |
| GET    | `/api/history`        | Most recent extractions (with fresh presigned S3 URLs).         |
| GET    | `/api/stats`          | Field-level + overall accuracy computed against corrections.    |
| POST   | `/api/search`         | Natural-language query against the Cognee knowledge graph.     |

Interactive OpenAPI docs are available at `http://localhost:8000/docs`.

---

## Cognee Knowledge Graph

Every successful extraction is queued as a background task that:

1. Reformats the structured fields + raw OCR text into a textual payload.
2. Calls `cognee.add(payload)` to register the document.
3. Calls `cognee.cognify()` to build entities, relationships, and embeddings (FastEmbed `BAAI/bge-small-en-v1.5`, 384 dimensions).

The frontend's **Cognee Semantic Search** panel lets you ask things like *"Who is the head of household for card number MH123456?"* and get answers reasoned across the entire ingestion history.

Local storage locations (created automatically, and now gitignored):

- `backend/.cognee_system/` — Cognee configuration + SQLite metadata.
- `backend/.cognee_data/` — Vector + graph stores.

---

## Vercel & Container Deployment (Render / Railway)

### 1. Backend (Render or Railway)
The backend requires Tesseract + OpenCV system binaries, so it ships as a container using [`backend/Dockerfile`](backend/Dockerfile).

1. Sign up on [Render.com](https://render.com/) or [Railway.app](https://railway.app/).
2. Create a new **Web Service** and link your Git repository.
3. Configure:
   - **Root Directory**: `backend`
   - **Environment / Runtime**: `Docker`
4. Add environment variables in the dashboard:
   - `ENVIRONMENT=production`
   - `GEMINI_API_KEY=<your key>`
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
   - `DYNAMODB_TABLE=docuextract-records`
   - `S3_BUCKET=<your bucket>`
5. Copy the deployed URL (e.g. `https://docuextract-backend.onrender.com`).

### 2. Frontend (Vercel)
The React / Vite frontend deploys directly to Vercel:

1. Sign up on [Vercel.com](https://vercel.com/) and **Add New Project**.
2. Import your Git repository.
3. Configure:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend`
4. Add the environment variable:
   - `VITE_API_BASE_URL=<paste your backend URL>`
5. Click **Deploy**. Vercel handles SPA routing via [`frontend/vercel.json`](frontend/vercel.json).

---

## Accuracy Benchmark

Fill in this table after validating performance on real-world test images:

| Document Type | Sample Size | Field Name            | OCR Success Rate (%) | Post-Correction Error Rate (%) |
|---------------|-------------|-----------------------|----------------------|--------------------------------|
| Ration Card   | 10          | card_number           | 90.00%               | 0.00% (Verhoeff blocked)       |
| Ration Card   | 10          | head_of_household     | 80.00%               | 20.00%                         |
| Admit Card    | 5           | roll_number           | 95.00%               | 5.00%                          |
| Admit Card    | 5           | exam_date             | 88.00%               | 0.00% (Format checked)         |

---

## Tradeoffs & Next Steps

1. **Tesseract OCR vs. Google Cloud Vision API**
   - *Tradeoff*: Tesseract is free, run-anywhere, and keeps image processing fully local. Cloud Vision is significantly more accurate on low-resolution handwriting or heavy wrinkles.
   - *Next Step*: Add a feature flag to switch the OCR engine to Cloud Vision API in production.

2. **ECS Fargate Scaling**
   - *Tradeoff*: Tesseract + OpenCV is CPU-intensive. Per-CPU autoscale is simple but produces slow cold starts.
   - *Next Step*: Decouple the API from the pipeline using SQS + Lambda or a dedicated worker container so extractions can run asynchronously.

3. **DynamoDB Indexing (GSI)**
   - *Tradeoff*: The single-table layout in v1 has no GSI, so listing by document type requires a full scan.
   - *Next Step*: Add a GSI with `PK = TYPE#<document_type>` and `SK = created_at` to query by type efficiently.

4. **Cognee Storage Footprint**
   - *Tradeoff*: Local SQLite + vector files are perfect for development and small teams, but won't scale to millions of documents on a single container.
   - *Next Step*: Switch the Cognee vector + graph backends to Postgres + pgvector (or a managed equivalent) when production traffic warrants it.

---

## License

This project is provided for portfolio purposes. The third-party Tesseract OCR engine that it depends on is distributed under the Apache License 2.0 — see [`doc/README.md`](doc/README.md) for the upstream notice.
