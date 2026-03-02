# FilmGraph
Knowledge Graph system grounding AI agents in formal semantics. Features automated Wikidata ETL, SHACL-based data governance, and a GraphRAG pipeline to eliminate LLM hallucinations. Built with a decoupled FastAPI/Next.js architecture to solve the explainability gap in modern AI systems.

---

***Try it here*** 👉 https://filmgraph-ai.vercel.app/

---

## 🚀 The Core Concept
Most movie searches are keyword-based. **FilmGraph** is relationship-based. It uses a Knowledge Graph to understand how directors, actors, and genres are interconnected, allowing for complex queries, such as:
* *"How many times has Robert De Niro worked with Al Pacino?"*
* *"Which directors have worked with Leonardo DiCaprio?"*
* *"List all 90s films under 100 minutes."*

## 🛠️ Tech Stack
* **Knowledge Graph:** RDF / Turtle (`.ttl`)
* **Logic & Validation:** SHACL, RDFS Inference
* **Data Processing:** Python + `rdflib` + Wikidata API
* **Inference & Logic:** OpenAI GPT-4o-mini
* **Backend:** FastAPI (Python)
* **Frontend:** React (Next.js), Tailwind CSS, Shadcn/UI

## ⚙️ How it Works

### 1. Data Provenance & ETL
The [`production_graph.ttl`](backend/production_graph.ttl) is the result of a custom Python pipeline:
* **Seed Data:** Began with a curated [`imdb_100.csv`](imdb_100.csv) containing the top 100 films.
* **Ontology Expansion:** Using `rdflib`, the pipeline extracted all directors from the seed set and performed a **Wikidata SPARQL crawl** to retrieve their entire filmographies, drastically expanding the graph's depth.
* **Transformation:** Complex Wikidata P-nodes were mapped to the [ defined schema](ontology/schema.ttl) (e.g., `:directedBy`, `:actedIn`). This can be seen in the script [`ingest_wikidata.py`](scripts/ingest_wikidata.py)
* **Validation & Inference:** Applied **SHACL** to validate data integrity and used RDF inference to materialise transitive relationships (like `:coDirectedWith`), ensuring the graph is optimised for LLM navigation. This can be seen in the script [`validate_and_infer.py`](scripts/validate_and_infer.py)

### 2. The GraphRAG Pipeline
1. **Natural Language Parsing:** The user asks a question in the UI.
2. **SPARQL Generation:** The LLM receives the question along with the **Graph Schema** (Ontology) and generates a precise SPARQL query.
3. **Graph Execution:** The Python backend executes the query against the local RDF graph.
4. **Data Synthesis:** Raw triples are sent back to the LLM to be summarised into a human-readable, grounded answer.

## 🕵️ Known Limitations
This project operates under a **Closed World Assumption**. Unlike a standard chatbot, this assistant is strictly bound by the triples in the local `.ttl` file.

### Data Constraints
* **Dataset Horizon:** The current knowledge graph is a curated subset of film history. If an actor or film is missing from the `.ttl` file, the system will not "fill in the gaps" using AI training data.
* **Schema Rigidity:** Queries rely on specific predicates (e.g., `:coDirectedWith`). While the LLM is mapped to the specific ontology, non-standard relationships may return empty sets.

### Preventing Hallucinations
* **Fact-Checking:** If a SPARQL query returns no rows, the system is instructed to report "No information found" rather than hallucinating.
* **Technical Trace:** Tthe UI includes a collapsible "View SPARQL" drawer. This allows for manual verification of the logic used to traverse the graph.
