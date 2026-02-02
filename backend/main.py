from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rdflib import Graph, Namespace, URIRef
import os

app = FastAPI()

# 1. Enable CORS so your Next.js frontend can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, you'd limit this to your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Setup RDF Graph
CINE = Namespace("http://filmgraph.pro/ontology/")
g = Graph()

# Path to your production graph
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRAPH_PATH = os.path.join(BASE_DIR, "../ontology/production_graph.ttl")

@app.on_event("startup")
def load_ontology():
    print(f"Loading knowledge graph from {GRAPH_PATH}...")
    if os.path.exists(GRAPH_PATH):
        g.parse(GRAPH_PATH, format="turtle")
        print(f"✅ Loaded {len(g)} triples.")
    else:
        print("❌ Error: production_graph.ttl not found!")

# 3. The Search Endpoint
@app.get("/movies")
def get_movies(limit: int = 10):
    # This SPARQL query finds movies and their release years
    query = """
    SELECT ?title ?year WHERE {
        ?m a <http://filmgraph.pro/ontology/Film> ;
           <http://www.w3.org/2000/01/rdf-schema#label> ?title ;
           <http://filmgraph.pro/ontology/releaseYear> ?year .
    }
    LIMIT %d
    """ % limit
    
    results = g.query(query)
    return [{"title": str(row.title), "year": int(row.year)} for row in results]

@app.get("/")
def read_root():
    return {"status": "Knowledge Graph API is online"}