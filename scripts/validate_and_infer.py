import os
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, RDF
from pyshacl import validate

BASE_DIR = Path(__file__).resolve().parent
ONTOLOGY_DIR = (BASE_DIR / "../ontology").resolve()

SCHEMA_FILE = ONTOLOGY_DIR / "schema.ttl"
DATA_FILE = ONTOLOGY_DIR / "output_graph.ttl"
SHAPES_FILE = ONTOLOGY_DIR / "shapes.ttl"
OUTPUT_FILE = ONTOLOGY_DIR / "production_graph.ttl"

def cleanup_duplicates(graph):
    CINE = Namespace("http://filmgraph/ontology/")
    
    films = set(graph.subjects(predicate=CINE.releaseYear))
    
    for film in films:
        years = sorted(list(graph.objects(film, CINE.releaseYear)))
        if len(years) > 1:
            print(f"Squashing duplicate years for {film.split('/')[-1]}: kept {years[0]}")
            # Remove ALL years first
            graph.remove((film, CINE.releaseYear, None))
            # Re-add only the earliest one
            graph.add((film, CINE.releaseYear, years[0]))

def run_pipeline():
    print(f"Checking paths in: {ONTOLOGY_DIR}")
    
    if not DATA_FILE.exists():
        print(f"❌ Critical Error: {DATA_FILE.name} not found! Run the ingest script first.")
        return

    data_graph = Graph()
    data_graph.parse(str(DATA_FILE), format="turtle")
    if SCHEMA_FILE.exists():
        data_graph.parse(str(SCHEMA_FILE), format="turtle")

    cleanup_duplicates(data_graph)

    shacl_graph = None
    if SHAPES_FILE.exists():
        print("Loading Validation Shapes...")
        shacl_graph = Graph()
        shacl_graph.parse(str(SHAPES_FILE), format="turtle")
    else:
        print(f"Warning: {SHAPES_FILE.name} not found. Skipping validation.")

    print("Running Validation and OWL Inference...")
    conforms, results_graph, results_text = validate(
        data_graph,
        shacl_graph=shacl_graph,
        inference='owlrl', 
        serialize_report_graph=True
    )

    if conforms:
        print("✅ Validation Success: Data is clean and consistent.")
    else:
        print("❌ Validation Errors Found:")
        print(results_text)

    before_count = len(data_graph)
    data_graph.serialize(destination=str(OUTPUT_FILE), format="turtle")
    after_count = len(data_graph)
    
    print(f"✅ Success! Enriched graph saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_pipeline()