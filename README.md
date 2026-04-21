# 🏞️ FRA Atlas AI — Intelligent Forest Rights Monitoring & Decision Support System  


> **Digitizing Forest Rights for Transparent, Data-Driven Governance.**  
> FRA Atlas AI automates the verification of forest land rights, integrates geospatial and satellite data, and powers a Decision Support System (DSS) to link FRA patta holders with government schemes.

---

## 🧠 Problem Statement  

| **Issue** | **Description** |
|------------|----------------|
| **Fragmented Data** | FRA claims, GIS maps, and Census records exist separately and are mostly non-digital. |
| **Manual Verification** | Field staff verify documents manually without real-time map references. |
| **Lack of Transparency** | No centralized system exists to visualize granted titles or scheme eligibility. |
| **Objective** | Create an AI-powered, GIS-integrated, end-to-end FRA management platform with a decision-support layer. |

---

## 💡 Our Solution — *FRA Atlas AI Platform*  

| **Component** | **Description** |
|----------------|----------------|
| **OCR Automation** | Extracts and structures data from legacy paper FRA documents using Tesseract/Google Vision. |
| **AI Verification Engine** | Cleans and validates data via Pandas, Great Expectations, and LLM-based anomaly detection. |
| **Land Classification** | Identifies land types (forest, agriculture, pond, etc.) using ISRO Bhuvan API or custom CNN model. |
| **Geo-Mapping** | Displays approved claims on an interactive map using Mapbox + PostGIS. |
| **DSS Query Interface** | Officers can ask natural language queries (via LangChain + MCP) — e.g., *“Show all PM-KISAN eligible families in Village X.”* |
| **Citizen Portal** | Enables tracking claim status and viewing approved maps (no edit access). |

---

## 🧩 Core Features  

| **Feature** | **Description** |
|--------------|----------------|
| 🧾 **Document Digitization** | Automated OCR and data structuring from scanned FRA documents. |
| 🧹 **Data Cleaning Pipeline** | Validates extracted text using Pandas, Regex, Great Expectations, and LLM. |
| 🛰️ **Land Type Classification** | Classifies land via ISRO Bhuvan or a CNN model trained on Sentinel-2 / EuroSAT data. |
| 🗺️ **FRA Atlas Visualization** | Approved claims plotted on an interactive, zoomable GIS map. |
| 🤖 **Decision Support System (DSS)** | LLM-powered query engine to layer Central Schemes (PM-KISAN, MGNREGA, etc.) over FRA data. |
| 📬 **Smart Notifications** | Sends SMS/email to eligible citizens when new schemes are introduced. |
| 👥 **Citizen Transparency Portal** | Public dashboard showing approved claims (non-confidential info only). |

---

## ⚙️ Tech Stack  

| **Layer** | **Technology Used** |
|------------|--------------------|
| **Frontend** | React.ts, Redux Toolkit / React Query, Mapbox GL JS, TailwindCSS |
| **Backend** |  FastAPI, REST APIs, JWT Auth, MCP middleware |
| **AI / ML** | OCR (Tesseract/Google Vision), CNN (TensorFlow/Keras), LLM (LangChain + Google-Gemini) |
| **Data Cleaning** | Pandas, Great Expectations, Regex |
| **Geo / Spatial** | ISRO Bhuvan API, Google Earth Engine, PostGIS |
| **Database** | PostgreSQL + PostGIS, Redis (caching), Elasticsearch (search) |
| **Notifications** | Twilio / AWS SNS for SMS |
| **Deployment** | Docker, NGINX, GitHub Actions CI/CD |

---

## 🏗️ System Architecture  

| **Step** | **Process** |
|-----------|-------------|
| 1️⃣ | Officer logs in → authentication check. |
| 2️⃣ | Uploads scanned FRA document → triggers OCR. |
| 3️⃣ | Extracted text cleaned using Pandas + LLM verification. |
| 4️⃣ | Land coordinates checked via ISRO Bhuvan / CNN model. |
| 5️⃣ | If verified → record stored in PostgreSQL + plotted on GIS map. |
| 6️⃣ | DSS allows NL queries like “Families eligible for PM-KISAN in District A.” |
| 7️⃣ | Eligible citizens notified automatically by SMS/email. |

---

## 📂 Folder Structure  

| **Folder** | **Description** |
|-------------|----------------|
| `Backend/` | FastAPI backend, OCR & ML services, API routes, database logic |
| `routers/` | REST endpoints for upload, DSS queries, and classification |
| `services/` | Scheme overlay service, OCR extraction, and ML inference |
| `Frontend/` | React dashboard for officers and citizens |
| `src/pages/` | Login, Dashboard, Upload, DSS Query, Citizen Map |
| `src/components/ui/` | Header, Chatbot, Layouts, and protected route handlers |
| `models/` | CNN model for land classification |
| `fra.db` | PostgreSQL database file (with PostGIS) |

---

## 🚀 Quick Start  

| **Step** | **Command** |
|-----------|-------------|
| **1️⃣ Clone Repository** | `git clone https://github.com/Priyankagh24/FRA-Atlas-AI.git` |
| **2️⃣ Install Backend Deps** | `pip install -r requirements.txt` |
| **3️⃣ Run Backend Server** | `uvicorn main:app --reload` |
| **4️⃣ Launch Frontend** | `cd Frontend && npm install && npm run dev` |
| **5️⃣ Access in Browser** | `http://localhost:5173` |

---

## 🧠 Model & Data References  

| **Resource** | **Link** |
|---------------|----------|
| **EuroSAT Sentinel-2 Dataset** | [https://github.com/phelber/EuroSAT](https://github.com/phelber/EuroSAT) |
| Deep Learning for Land Use & Cover Classification | [arXiv:1709.00029](https://arxiv.org/abs/1709.00029) |
| Sentinel-2 Land Cover Classification with CNNs | [MDPI Remote Sensing Journal](https://www.mdpi.com/2072-4292/12/15/2495) |
| Forest Rights Act, 2006 | [IndiaCode PDF](https://www.indiacode.nic.in/bitstream/123456789/8311/1/a2007-02.pdf) |
| FRA Rules & Guidelines | [Ministry of Tribal Affairs](https://tribal.nic.in/FRA/data/FRARulesBook.pdf) |
| ISRO Bhuvan Portal | [https://bhuvan.nrsc.gov.in/ngmaps](https://bhuvan.nrsc.gov.in/ngmaps) |


---

## 🔒 Privacy & Data Ethics  

| **Principle** | **Measure** |
|----------------|-------------|
| Data Minimization | Only essential details are displayed publicly. |
| Access Control | Role-based authorization for officers, admins, and citizens. |
| Transparency | All approved FRA claims visible to public in anonymized form. |
| Audit Trail | Every action (upload, approval, DSS query) is logged for accountability. |

---

## 🧭 Future Scope  

| **Feature** | **Description** |
|--------------|----------------|
| 🌐 Multi-Language NLP | Add Hindi & tribal dialects to DSS query engine. |
| 🛰️ Real-Time Satellite Sync | Live update from ISRO Sentinel datasets. |
| 🤝 Scheme Integration API | Automated scheme mapping for all ministries. |
| 📱 Mobile App | Flutter app for citizen & officer access. |
| 🧮 Predictive DSS | ML-based recommendations for pending approvals. |


---

## 🧾 References  

See full list of datasets and legal references in [Model & Data References](https://github.com/phelber/EuroSAT) section.  


