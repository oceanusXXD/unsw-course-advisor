## UNSW Course Advisor 🤖🎓  
[中文](./README.md) | [Deutsch](COMING SOON) | [日本語](COMING SOON) | [Español](COMING SOON)  
An AI-powered, personalized course recommendation system for UNSW students, built with a modern RAG (Retrieval-Augmented Generation) pipeline. This project aims to replace manual Handbook searches with intelligent, evidence-based course suggestions.  

---

### 🎯 Core Idea  
Navigating the UNSW Handbook to find the right courses can be overwhelming. This project automates the discovery process by combining:  
- A web crawler  
- A vector database  
- Large Language Models (LLMs)  

**For Students**: Get personalized course suggestions based on your major, completed courses, and interests.  
**For Advisors & Staff**: A powerful tool for querying course data and understanding curriculum relationships.  

**Core Principle**:  
1. Crawl official course data  
2. Ingest it into a searchable database  
3. Use a RAG service to generate human-like advice, backed by real data.  

---

### ✨ Key Features  
- **Always Up-to-Date**: Periodic crawls fetch the latest course information.  
- **Personalized Recommendations**: Tailored to academic profile (major, completed courses) and interests (e.g., "AI", "Systems Engineering").  
- **Explainable AI**: Justified recommendations with snippets from course overviews, prerequisites, or notes.  
- **Interactive UI**: Streamlit interface for instant advice.  
- **Extensible & Modular**: Clean, decoupled architecture.  

---

### 🛠️ Tech Stack  
#### 🏛️ System Architecture  
**High-Level Modules**:  
- `crawler/`: Scripts to fetch course URLs and details.  
- `data/`: Stores raw crawled JSON and structured data.  
- `ingest/`: Parses data, populates DB, generates embeddings.  
- `retrieval/`: Queries the vector database.  
- `rag_service/`: Core RAG API for recommendations.  
- `ui/`: Streamlit/Django frontend.  
- `tests/`: Unit and integration tests.  
- `ops/`: Dockerfiles, deployment scripts.  

---

### 🚀 Getting Started  
#### Prerequisites  
- Python 3.9+  
- Docker and Docker Compose  
- PostgreSQL + Vector DB (e.g., ChromaDB)  
- LLM API Key (e.g., OpenAI)  

#### 1. Installation
```
bash
pip install -r requirements.txt
```
#### 2. End-to-End Workflow  
**Step 1: Crawl Course Data**  
Fetch course URLs, then crawl details (with anti-scraping measures).  

**Step 2: Ingest and Embed Data**  
- Processes raw JSON → PostgreSQL.  
- Generates embeddings → Vector DB.  

**Database Schema**:  
- `subjects`: Subject codes/names (e.g., COMP, MATH).  
- `courses`: Core course info (code, title, credits).  
- `course_details`: Overview, notes, delivery methods.  
- `embeddings`: Text chunks + vectors.  

**Step 3: Run RAG API Service**  
Key Endpoints:  
- `POST /api/recommend`: Main recommendation endpoint.  
- `GET /api/course/{code}`: Fetch course details.  
- `GET /api/search?query=...`: Vector search for snippets.  

**Step 4: Launch Streamlit UI**
```bash
streamlit run ui/app.py
Navigate to `http://localhost:8501`. 
```

---

### 📈 Roadmap & Future Improvements  
- [ ] Enhanced Student Profiling: Hybrid semantic + collaborative filtering.  
- [ ] Advanced Relationship Mapping: Course dependency graphs (LangGraph).  
- [ ] Confidence Scoring: Prerequisite alignment + difficulty risk.  
- [ ] Timetable Simulation: Check clashes/credit loads.  
- [ ] Chrome Extension: Overlay recommendations on Handbook.  
- [ ] A/B Testing Framework: Optimize prompts/retrieval models.  
- [ ] Semantic Clustering: Flag overlapping courses.  

---

### 🤝 Contributing  
1. Fork the Project.  
2. Create a Feature Branch (`git checkout -b feature/AmazingFeature`).  
3. Commit Changes (`git commit -m 'Add some AmazingFeature'`).  
4. Push to Branch (`git push origin feature/AmazingFeature`).  
5. Open a Pull Request.  

---

### 📄 License  
Distributed under the **MIT License**. See `LICENSE` for details.