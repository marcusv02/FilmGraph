import pandas as pd
import requests
import time
import os
import random
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD, RDFS

# 1. Configuration
WD_ENDPOINT = "https://query.wikidata.org/sparql"
CINE = Namespace("http://filmgraph.pro/ontology/")

def get_stealth_headers():
    # These headers mimic a real Chrome browser on Windows perfectly
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/sparql-results+json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://query.wikidata.org/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive"
    }

def fetch_wikidata_by_imdb(session, imdb_title_id):
    query = f"""
    SELECT ?movie ?movieLabel ?directorLabel ?year ?genreLabel WHERE {{
      ?movie wdt:P345 "{imdb_title_id}".
      OPTIONAL {{ ?movie wdt:P57 ?director. ?director rdfs:label ?directorLabel. FILTER(lang(?directorLabel) = "en") }}
      OPTIONAL {{ ?movie wdt:P577 ?date. BIND(YEAR(?date) AS ?year) }}
      OPTIONAL {{ ?movie wdt:P136 ?genre. ?genre rdfs:label ?genreLabel. FILTER(lang(?genreLabel) = "en") }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """

    params = {
        "query": query,
        "format": "json"
    }

    try:
        # Use the session to make the request (keeps the connection alive)
        response = session.get(WD_ENDPOINT, params=params, headers=get_stealth_headers(), timeout=10)
        
        if response.status_code == 429:
            print(f"⏳ Rate limited on {imdb_title_id}. Pausing for 10s...")
            time.sleep(10)
            return fetch_wikidata_by_imdb(session, imdb_title_id)

        if response.status_code == 403:
            print(f"🚫 403 Forbidden on {imdb_title_id}. (IP might still be blocked)")
            return None

        return response.json()

    except Exception as e:
        print(f"❌ Error fetching {imdb_title_id}: {e}")
        return None

def build_graph(csv_path):
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"❌ Error: Could not find CSV at {csv_path}")
        return Graph()

    g = Graph()
    g.bind("cine", CINE)
    
    # Initialize a Session (re-uses TCP connection like a browser)
    session = requests.Session()

    print(f"🚀 Starting ingestion of {len(df)} movies...")
    
    # for index, row in df.iterrows():
    #     imdb_title_id = row['imdb_title_id']
    #     print(f"Processing {index + 1}/{len(df)}: {imdb_title_id}...")
        
    #     data = fetch_wikidata_by_imdb(session, imdb_title_id)
        
    #     if not data or 'results' not in data or not data['results']['bindings']:
    #         print(f"   ⚠️ No data found.")
    #         continue
        
    #     for res in data['results']['bindings']:
    #         if 'movieLabel' in res:
    #             # Clean strings to make safe URIs
    #             movie_label = res['movieLabel']['value']
    #             movie_name = movie_label.replace(" ", "_").replace("'", "").replace(".", "")
    #             movie_uri = URIRef(CINE[movie_name])
                
    #             g.add((movie_uri, RDF.type, CINE.Film))
    #             g.add((movie_uri, CINE.imdbId, Literal(imdb_title_id)))
    #             g.add((movie_uri, RDFS.label, Literal(movie_label))) # Add readable label
            
    #             if 'directorLabel' in res:
    #                 director_label = res['directorLabel']['value']
    #                 director_name = director_label.replace(" ", "_").replace("'", "")
    #                 director_uri = URIRef(CINE[director_name])
                    
    #                 g.add((movie_uri, CINE.directedBy, director_uri))
    #                 g.add((director_uri, RDF.type, CINE.Person))
    #                 g.add((director_uri, RDFS.label, Literal(director_label)))

    #             if 'year' in res:
    #                 # Wikidata sometimes returns dates like 1994-01-01T00:00:00Z
    #                 # We want just 1994
    #                 year_val = res['year']['value']
    #                 g.add((movie_uri, CINE.releaseYear, Literal(int(year_val), datatype=XSD.integer)))
        
    #     # Random sleep to look human (between 1 and 3 seconds)
    #     time.sleep(random.uniform(1.0, 3.0))

    # return g

    for index, row in df.iterrows():
        imdb_title_id = row['imdb_title_id']
        print(f"Processing {index + 1}/{len(df)}: {imdb_title_id}...")
        
        data = fetch_wikidata_by_imdb(session, imdb_title_id)
        
        if not data or 'results' not in data or not data['results']['bindings']:
            print(f"   ⚠️ No data found.")
            continue
        
        # --- NEW: Aggregation Logic ---
        # We use sets to avoid duplicates during the collection phase
        movie_labels = set()
        directors = {} # Map name -> label for URI consistency
        years = set()

        for res in data['results']['bindings']:
            if 'movieLabel' in res:
                movie_labels.add(res['movieLabel']['value'])
            if 'directorLabel' in res:
                d_label = res['directorLabel']['value']
                d_uri_name = d_label.replace(" ", "_").replace("'", "")
                directors[d_uri_name] = d_label
            if 'year' in res:
                years.add(int(res['year']['value']))

        # --- NEW: Conflict Resolution & Graph Writing ---
        if movie_labels:
            # 1. Resolve Movie Identity
            # We take the first label found as the primary
            primary_label = list(movie_labels)[0]
            movie_name = primary_label.replace(" ", "_").replace("'", "").replace(".", "")
            movie_uri = URIRef(CINE[movie_name])
            
            g.add((movie_uri, RDF.type, CINE.Film))
            g.add((movie_uri, CINE.imdbId, Literal(imdb_title_id)))
            g.add((movie_uri, RDFS.label, Literal(primary_label)))

            # 2. Resolve Year (The "Earliest Year" Rule)
            if years:
                earliest_year = min(years)
                g.add((movie_uri, CINE.releaseYear, Literal(earliest_year, datatype=XSD.integer)))
                if len(years) > 1:
                    print(f"   📅 Resolved {len(years)} dates to earliest: {earliest_year}")

            # 3. Add Directors
            for d_uri_part, d_label in directors.items():
                director_uri = URIRef(CINE[d_uri_part])
                g.add((movie_uri, CINE.directedBy, director_uri))
                g.add((director_uri, RDF.type, CINE.Person))
                g.add((director_uri, RDFS.label, Literal(d_label)))

        # Random sleep to look human
        time.sleep(random.uniform(1.0, 2.5))

    return g

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_file = os.path.join(script_dir, "../imdb_100.csv")
    output_file = os.path.join(script_dir, "../ontology/output_graph.ttl")

    my_graph = build_graph(csv_file)
    
    print(f"💾 Saving to: {output_file}")
    my_graph.serialize(destination=output_file, format="turtle")
    print("✅ Success! Graph serialized.")