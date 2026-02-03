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

        # Only the earliest year (The Original Release)
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

def expand_by_directors(session, g):
    print("\nStarting Phase 2: Semantic Expansion...")
    directors = list(g.subjects(RDF.type, CINE.Person))
    
    for d_uri in directors:
        d_name = str(g.value(d_uri, RDFS.label))
        print(f"Expanding: {d_name}")

        query = f"""
        SELECT ?movie ?movieLabel ?year ?imdbId WHERE {{
          ?movie wdt:P57 ?dir .
          ?dir rdfs:label "{d_name}"@en .
          ?movie wdt:P345 ?imdbId .
          ?movie wdt:P31 wd:Q11424 . # Filter for FILMS only
          OPTIONAL {{ ?movie wdt:P577 ?date. BIND(YEAR(?date) AS ?year) }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        """
        try:
            response = session.get(WD_ENDPOINT, params={'query': query, 'format': 'json'}, headers=get_stealth_headers())
            data = response.json()
            
            # Temporary storage to deduplicate years for THIS director's movies
            movie_cache = {} # movie_uri -> {label, imdb, years_set}

            for res in data['results']['bindings']:
                m_label = res['movieLabel']['value']
                m_uri = URIRef(CINE[m_label.replace(" ", "_").replace("'", "").replace(".", "")])
                
                if m_uri not in movie_cache:
                    movie_cache[m_uri] = {
                        'label': m_label,
                        'imdb': res.get('imdbId', {}).get('value'),
                        'years': set()
                    }
                
                if 'year' in res:
                    movie_cache[m_uri]['years'].add(int(res['year']['value']))

            # Now add the "Cleaned" records to the actual graph
            for m_uri, info in movie_cache.items():
                g.add((m_uri, RDF.type, CINE.Film))
                g.add((m_uri, RDFS.label, Literal(info['label'])))
                g.add((m_uri, CINE.directedBy, d_uri))
                
                if info['imdb']:
                    g.add((m_uri, CINE.imdbId, Literal(info['imdb'])))
                
                if info['years']:
                    # SKEPTICISM: Take only the earliest year found
                    earliest_year = min(info['years'])
                    g.add((m_uri, CINE.releaseYear, Literal(earliest_year, datatype=XSD.integer)))

            time.sleep(0.8) 
        except Exception as e:
            print(f" ❌ Failed to expand {d_name}: {e}")

    return g

if __name__ == "__main__":
    print("Phase 1: Ingesting 100 Seed Movies...")
    session = requests.Session()
    first_graph = build_graph("imdb_100.csv")
    
    # NEW: Phase 2 Expansion
    print(f"\n✅ Phase 1 Complete. Graph has {len(first_graph)} triples.")
    final_graph = expand_by_directors(session, first_graph)
    
    print(f"\n✅ Phase 2 Complete. Final Graph has {len(final_graph)} triples.")
    
    # Save the giant graph
    final_graph.serialize(destination="ontology/output_graph.ttl", format="turtle")
    print("Everything saved to ontology/output_graph.ttl")