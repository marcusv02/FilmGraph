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

    # try:
    #     # Step 1: Text-to-SPARQL
    #     response = client.chat.completions.create(
    #         model="gpt-4o-mini",
    #         messages=[
    #             {"role": "system", "content": system_prompt},
    #             {"role": "user", "content": request.question}
    #         ]
    #     )
    #     query = response.choices[0].message.content.strip().replace("```sparql", "").replace("```", "")

    #     # Step 2: Execute on Graph
    #     results = g.query(query)
        
    #     # Step 3: Raw and Natural Language Answer
    #     actual_results = [list(row) for row in results]
    #     raw_data_list = [[str(value) for value in item] for item in actual_results]
    #     raw_data_string = "\n".join([", ".join([str(v).split('/')[-1].split('#')[-1] for v in row]) for row in actual_results])

    #     if not raw_data_list:
    #         return {
    #             "answer": "The knowledge graph doesn't have any records that match that specific question.",
    #             "sparql": query,
    #             "raw_data": []
    #         }
        
    #     summary = client.chat.completions.create(
    #         model="gpt-4o-mini",
    #         messages=[
    #             {"role": "system", "content": "You are a helpful film expert. Use the provided Database Results to answer the question. If the data is not in the results, say you don't know."},
    #             {"role": "user", "content": f"User Question: {request.question} \nDatabase Results:\n{raw_data_string}"}
    #         ]
    #     )

    #     return {
    #         "answer": summary.choices[0].message.content,
    #         "sparql": query,
    #         "raw_data": raw_data_string
    #     }

    # except Exception as e:
    #     print(f"Error: {e}")
    #     raise HTTPException(status_code=500, detail="The AI failed to query the graph.")

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