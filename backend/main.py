import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rdflib import Graph, Namespace
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

CINE = Namespace("http://filmgraph/ontology/")
g = Graph()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPH_PATH = "production_graph.ttl"

@app.on_event("startup")
def load_ontology():
    current_dir = os.getcwd()
    abs_path = os.path.abspath(GRAPH_PATH)
    
    if os.path.exists(GRAPH_PATH):
        g.parse(GRAPH_PATH, format="turtle")

        print(f"✅ SUCCESS: Loaded {len(g)} triples.")
    else:
        print(f"❌ ERROR: File not found at {abs_path}!")

class QuestionRequest(BaseModel):
    question: str

# 3. The AI Search Endpoint
@app.post("/ask")
async def ask_ai(request: QuestionRequest):
    system_prompt = f"""
    You are a SPARQL expert for the FilmGraph.
    IMPORTANT: You MUST start your query with this EXACT line:
    PREFIX : <http://filmgraph/ontology/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    Classes: :Film, :Actor, :Director, :Genre, :Person
    
    Object Properties:
    - :directedBy / :directed (Inverse)
    - :hasActor / :actedIn (Inverse)
    - :hasGenre (Film -> Genre)
    - :hasPerson (Film -> Person)
    - :workedWith (Person -> Person)
    - :coStarredWith (Actor -> Actor)
    - :coDirectedWith (Director -> Director)
    
    Data Properties:
    - :duration (minutes as integer)
    - :year (integer)
    
    Rules:
    - Use ONLY the 'Graph Data' provided. 
    - NEVER mention any other name unless it appears in the 'Graph Data' list.
    - Do not provide 'background info' or 'historical context.'
    - Return ONLY the SPARQL query code.
    - Always use rdfs:label for name searches.
    - For relationships, favour inferred properties like :coStarredWith.
    """
#     system_prompt = f"""
# You are a SPARQL expert for the FilmGraph, a Knowledge Graph based on the top 100 films of all time.
# Your task is to translate natural language questions into valid SPARQL queries using the provided schema.

# ### 1. NAMESPACES & PREFIXES
# You MUST start every query with:
# PREFIX : <http://filmgraph/ontology/>
# PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

# ### 2. GRAPH STRUCTURE (SCHEMA)
# - **Classes**: :Film, :Actor, :Director, :Genre, :Person (Actor and Director are subclasses of Person).
# - **Core Connections**:
#     * :Film :directedBy :Director | :Director :directed :Film
#     * :Film :hasActor :Actor     | :Actor :actedIn :Film
#     * :Film :hasGenre :Genre
#     * :Film :hasPerson :Person
# - **Symmetric Shortcuts (Property Chains)**:
#     * :workedWith (Person <-> Person): Use for any collaboration.
#     * :coStarredWith (Actor <-> Actor): Specifically for actors in the same film.
#     * :coDirectedWith (Director <-> Director): Specifically for directors of the same film.
# - **Data Properties**:
#     * :duration (Integer - minutes)
#     * :year (Integer - release year)

# ### 3. QUERY LOGIC RULES
# 1. **Label Matching**: Find entities by matching `rdfs:label`. Use `FILTER(CONTAINS(LCASE(?label), "text"))` for robustness.
# 2. **Path Connectivity (Critical)**: Ensure every variable in the WHERE clause is connected to another. Do NOT introduce "orphan" variables (like ?film) unless they are part of the join path between the subject and the result.
# 3. **Property Selection**: 
#    - Use "Shortcuts" (:workedWith) for general collaboration questions.
#    - Use "Core Connections" (:directedBy, :hasActor) ONLY when the user asks about specific Films or counts based on Films.
# 4. **Aggregation**: For "the most", use `SELECT ?label (COUNT(?target) AS ?count)`, GROUP BY ?label, ORDER BY DESC(?count), and LIMIT 1.
# 5. **Deduplication**: Use `SELECT DISTINCT` to avoid redundant results from the graph.

# ### 4. OUTPUT CONSTRAINTS
# - Do NOT provide conversational text, background info, or historical context.
# - If the question cannot be answered by the schema, say you don't know.
# - ALWAYS use DISTINCT to prevent real database duplicates.
# """

    try:
        # Step 1: Text-to-SPARQL
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.question}
            ]
        )
        query = response.choices[0].message.content.strip().replace("```sparql", "").replace("```", "")

        # Step 2: Execute on Graph
        results = g.query(query)
        actual_results = [list(row) for row in results]

        if not actual_results:
            return {
                "answer": "The knowledge graph doesn't have any records that match that specific question.",
                "sparql": query,
                "raw_data": ""
            }
        clean_rows = []
        for row in actual_results:
            clean_values = [str(v).split('/')[-1].split('#')[-1].replace('_', ' ') for v in row]
            clean_rows.append(", ".join(clean_values))
        
        # This is the string we show the AI and the user
        formatted_data_string = "\n".join(clean_rows)

        # Step 4: Final Summary
        summary = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": (
                "You are an expert film database assistant. I will provide 'Database Results' "
                "extracted from a Knowledge Graph. Your task is to summarize these results "
                "to answer the user's question. \n\n"
                "STRICT RULES:\n"
                "1. If Database Results are present, use them as the absolute truth.\n"
                "2. Do not add outside information or actors not listed in the data.\n"
                "3. If the results look like a list, format them nicely.\n"
                "4. If the results are empty, state that the database doesn't have that information."
                    )
                },
                {
                    "role": "user", 
                    "content": f"User Question: {request.question} \nDatabase Results:\n{formatted_data_string}"
                }
            ]
        )

        return {
            "answer": summary.choices[0].message.content,
            "sparql": query,
            "raw_data": formatted_data_string
        }

    except Exception as e:
        print(f"Error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/")
def read_root():
    return {"status": "Knowledge Graph API online", "triples": len(g)}