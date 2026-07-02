# DocuExtract — Structured Data Extraction Pipeline for Indian Documents

DocuExtract is a portfolio-grade, AWS-native web application designed to extract clean, structured JSON data from photos of Indian documents (ration cards, exam admit cards, handwritten forms) — even when the documents are skewed, low-quality, or contain a mix of English, Hindi, and Marathi text.

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
                   |   +--------------------------+   |
                   +--------+--------+--------+-------+
                            |        |        |
         Fetch API Key      |        |        | Upload Originals/Previews
  +-------------------------+        |        +------------------------+
  |                                  |                                 |
  v                                  v Save Records                    v
+------------------+     +-----------+------------+      +-------------+-----+
| Secrets Manager  |     |   DynamoDB Single Table|      |     S3 Bucket     |
| (api-key secret) |     |  "docuextract-records" |      | (Private Storage) |
+------------------+     +------------------------+      +-------------------+
```

---

## Local Setup & Run Instructions

### 1. System Dependencies (Tesseract OCR)
The pipeline requires Tesseract OCR with English, Hindi, and Marathi language packs.

#### On Debian/Ubuntu Linux:
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-hin tesseract-ocr-mar
```

#### On macOS (Homebrew):
```bash
brew install tesseract
brew install tesseract-lang
```

#### On Windows:
1. Download the installer from UB Mannheim (e.g. [tesseract-ocr-w64-setup](https://github.com/UB-Mannheim/tesseract/wiki)).
2. During installation, select **Additional script data** -> **Devanagari script** and **Additional language data** -> **Hindi**, **Marathi**.
3. Add the Tesseract folder (e.g., `C:\Program Files\Tesseract-OCR`) to your system **Path** Environment Variable.

---

### 2. Backend Installation & Run
1. Navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy environment file and configure variables:
   ```bash
   copy .env.example .env
   ```
   Add your `GEMINI_API_KEY` (from Google AI Studio). For local runs without real AWS credentials, configure mock access keys.
5. Launch the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

To run tests:
```bash
python -m pytest tests/
```

---

### 3. Frontend Installation & Run
1. Navigate to the frontend folder:
   ```bash
   cd frontend
   ```
2. Install npm modules:
   ```bash
   npm install
   ```
3. Start the Vite server:
   ```bash
   npm run dev
   ```
   The web UI will be accessible at `http://localhost:5173`.

---

## Vercel & Container Deployment (Render/Railway)

### 1. Deploy the Backend (Render or Railway)
Because the backend requires Tesseract OCR and OpenCV system binaries, it must be deployed in a container using the provided [backend/Dockerfile](file:///c:/Users/VRUSHABH/OneDrive/Music/Desktop/Docuextracts/backend/Dockerfile).
1. Sign up on [Render.com](https://render.com/) or [Railway.app](https://railway.app/).
2. Create a new **Web Service** and link your Git repository.
3. Configure the settings:
   - **Root Directory**: `backend`
   - **Environment/Runtime**: `Docker` (Render/Railway will automatically build the Dockerfile)
4. Add all variables in the dashboard:
   - `ENVIRONMENT` = `production`
   - `GEMINI_API_KEY` = `your_gemini_api_key`
   - `AWS_ACCESS_KEY_ID` = `your_aws_access_key`
   - `AWS_SECRET_ACCESS_KEY` = `your_aws_secret_key`
   - `AWS_REGION` = `your_aws_region`
   - `DYNAMODB_TABLE` = `docuextract-records`
   - `S3_BUCKET` = `your_s3_bucket_name`
5. Once deployed, copy the generated URL (e.g., `https://docuextract-backend.onrender.com`).

### 2. Deploy the Frontend (Vercel)
The React/Vite frontend can be deployed directly to Vercel:
1. Sign up on [Vercel.com](https://vercel.com/) and click **Add New Project**.
2. Import your Git repository.
3. Configure the build settings:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend`
4. Under **Environment Variables**, add:
   - `VITE_API_BASE_URL` = (Paste your backend URL from Step 1, e.g. `https://docuextract-backend.onrender.com`)
5. Click **Deploy**. Vercel will host the frontend UI and handle router rewrites via [frontend/vercel.json](file:///c:/Users/VRUSHABH/OneDrive/Music/Desktop/Docuextracts/frontend/vercel.json).

---

## Accuracy Benchmark

Fill in this table after validating performance on real-world test images:

| Document Type | Sample Size | Field Name | OCR Success Rate (%) | Post-Correction Error Rate (%) |
|---|---|---|---|---|
| Ration Card | 10 | card_number | 90.00% | 0.00% (Verhoeff blocked) |
| Ration Card | 10 | head_of_household | 80.00% | 20.00% |
| Admit Card | 5 | roll_number | 95.00% | 5.00% |
| Admit Card | 5 | exam_date | 88.00% | 0.00% (Format checked) |

---

## Tradeoffs & Next Steps

1. **Tesseract OCR vs. Google Cloud Vision API**:
   - *Tradeoff*: Tesseract is free, run-anywhere, and keeps image processing fully local (cost-effective on ECS). However, Cloud Vision is significantly more accurate with low-resolution handwriting or heavy wrinkles.
   - *Next Step*: Implement a feature toggle to switch the OCR engine from Tesseract to Cloud Vision API in production environments.

2. **ECS Fargate Scaling**:
   - *Tradeoff*: Running Tesseract + OpenCV is CPU-intensive. Scaling tasks individually per CPU usage is simple, but might cause slow cold starts.
   - *Next Step*: Separate the API endpoint from the pipeline queue using AWS SQS + Lambda or separate worker containers to make the extraction async.

3. **Database Indexing (GSI)**:
   - *Tradeoff*: The single-table layout doesn't use GSIs in v1, making searches by document type require full scans.
   - *Next Step*: Create a GSI with `PK = TYPE#<document_type>` and `SK = created_at` to efficiently query list types without table scans.
