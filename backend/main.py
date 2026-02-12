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
GRAPH_PATH = os.path.join(BASE_DIR, "../backend/production_graph.ttl")

@app.on_event("startup")
def load_ontology():
    print(f"⏳ Loading knowledge graph from {GRAPH_PATH}...")
    if os.path.exists(GRAPH_PATH):
        g.parse(GRAPH_PATH, format="turtle")
        g.bind("", CINE)
        print(f"✅ Loaded {len(g)} triples.")
    else:
        print(f"❌ Error: {GRAPH_PATH} not found!")

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
    - Return ONLY the SPARQL query code.
    - Always use rdfs:label for name searches.
    - For relationships, favour inferred properties like :coStarredWith.
    """

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
        
        # Step 3: Natural Language Answer
        raw_data = [str(row) for row in results]
        
        summary = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful film expert. Use the provided data to answer the user's question naturally."},
                {"role": "user", "content": f"User Question: {request.question} \n Database Results: {raw_data}"}
            ]
        )

        return {
            "answer": summary.choices[0].message.content,
            "sparql": query
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="The AI failed to query the graph.")

@app.get("/")
def read_root():
    return {"status": "Knowledge Graph API online", "triples": len(g)}