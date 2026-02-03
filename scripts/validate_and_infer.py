import os
from pathlib import Path
from rdflib import Graph
from pyshacl import validate

# 1. Direct Path Setup
BASE_DIR = Path(__file__).resolve().parent
ONTOLOGY_DIR = (BASE_DIR / "../ontology").resolve()

SCHEMA_FILE = ONTOLOGY_DIR / "schema.ttl"
DATA_FILE = ONTOLOGY_DIR / "output_graph.ttl"
SHAPES_FILE = ONTOLOGY_DIR / "shapes.ttl"  # Ensure this matches your filename!
OUTPUT_FILE = ONTOLOGY_DIR / "production_graph.ttl"

def run_pipeline():
    print(f"🧠 Checking paths in: {ONTOLOGY_DIR}")
    
    # 2. Safety Checks
    for f in [SCHEMA_FILE, DATA_FILE]:
        if not f.exists():
            print(f"❌ Critical Error: {f.name} not found!")
            return

    data_graph = Graph()
    data_graph.parse(str(SCHEMA_FILE), format="turtle")
    data_graph.parse(str(DATA_FILE), format="turtle")

    # 3. Load SHACL Shapes
    shacl_graph = None
    if SHAPES_FILE.exists():
        print("🛡️ Loading Validation Shapes...")
        shacl_graph = Graph()
        shacl_graph.parse(str(SHAPES_FILE), format="turtle")
    else:
        # This is the line causing your warning
        print(f"⚠️ Warning: {SHAPES_FILE.name} not found at {SHAPES_FILE}. Skipping validation.")

    # 4. Perform Validation & Inference
    print("🔍 Running Validation and OWL Inference...")
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

    # 5. Save the Enriched Graph
    data_graph.serialize(destination=str(OUTPUT_FILE), format="turtle")
    print(f"Success! Enriched graph saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_pipeline()