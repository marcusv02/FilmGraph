import pandas as pd
import time
import random
import requests
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, XSD

# 1. Setup
CINE = Namespace("http://filmgraph.pro/ontology/")
WD_ENDPOINT = "https://query.wikidata.org/sparql"

def get_stealth_headers():
    return {
        'User-Agent': 'FilmGraphBot/1.0 (Expert-Skeptic-Project) Python-requests',
        'Accept': 'application/sparql-results+json'
    }

def fetch_wikidata(session, imdb_id):
    query = f"""
    SELECT ?movie ?movieLabel ?directorLabel ?year WHERE {{
      ?movie wdt:P345 "{imdb_id}".
      ?movie wdt:P57 ?director.
      ?director rdfs:label ?directorLabel.
      OPTIONAL {{ ?movie wdt:P577 ?date. BIND(YEAR(?date) AS ?year) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      FILTER(LANG(?directorLabel) = "en")
    }}
    """
    try:
        response = session.get(WD_ENDPOINT, params={'query': query, 'format': 'json'}, headers=get_stealth_headers())
        return response.json()
    except Exception as e:
        print(f"   ❌ Error for {imdb_id}: {e}")
        return None

def build_graph(csv_path):
    g = Graph()
    g.bind("cine", CINE)
    df = pd.read_csv(csv_path)
    session = requests.Session()

    for index, row in df.iterrows():
        imdb_id = row['imdb_title_id']
        print(f"[{index+1}/100] Processing {imdb_id}...")
        
        raw_data = fetch_wikidata(session, imdb_id)
        if not raw_data or not raw_data['results']['bindings']:
            continue

        # --- DATA AGGREGATION & CONFLICT RESOLUTION ---
        years = set()
        directors = {} # Map names to URIs to avoid duplicates
        movie_label = None

        for item in raw_data['results']['bindings']:
            if not movie_label: 
                movie_label = item['movieLabel']['value']
            
            if 'year' in item:
                years.add(int(item['year']['value']))
            
            d_name = item['directorLabel']['value']
            d_uri_slug = d_name.replace(" ", "_").replace("'", "")
            directors[d_uri_slug] = d_name

        # --- WRITING TO GRAPH ---
        # Create a clean Movie URI
        m_slug = movie_label.replace(" ", "_").replace("'", "").replace(".", "")
        m_uri = URIRef(CINE[m_slug])

        g.add((m_uri, RDF.type, CINE.Film))
        g.add((m_uri, RDFS.label, Literal(movie_label)))
        g.add((m_uri, CINE.imdbId, Literal(imdb_id)))

        # SKEPTICISM APPLIED: Only the earliest year (The 'Original' Release)
        if years:
            g.add((m_uri, CINE.releaseYear, Literal(min(years), datatype=XSD.integer)))

        # Add Directors
        for slug, name in directors.items():
            d_uri = URIRef(CINE[slug])
            g.add((m_uri, CINE.directedBy, d_uri))
            g.add((d_uri, RDF.type, CINE.Person))
            g.add((d_uri, RDFS.label, Literal(name)))

        time.sleep(random.uniform(0.6, 1.2))
    
    return g

if __name__ == "__main__":
    print("🚀 Starting Smart Ingestion...")
    clean_graph = build_graph("imdb_100.csv")
    clean_graph.serialize(destination="ontology/output_graph.ttl", format="turtle")
    print("\n✅ Success! File saved to: ontology/output_graph.ttl")