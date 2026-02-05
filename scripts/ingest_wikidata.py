import pandas as pd
import time
import random
import requests
import re
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, XSD

# 1. Setup
CINE = Namespace("http://filmgraph.pro/ontology/")
WD_ENDPOINT = "https://query.wikidata.org/sparql"

def get_stealth_headers():
    return {
        'User-Agent': 'FilmGraphBot/1.0 (Expert-Skeptic-Project) Python-requests',
        'Accept': 'application/sparql-results+json'
    }

def clean_uri_slug(text):
    """Skeptic's Cleanse: Removes quotes and special chars that break RDF serializing."""
    if not text: return "Unknown"
    # Remove double quotes, single quotes, and dots
    clean = re.sub(r'["\'.]', '', text)
    # Replace spaces and slashes with underscores
    return clean.replace(" ", "_").replace("/", "_")

def fetch_wikidata(session, imdb_id):
    query = f"""
    SELECT ?movie ?movieLabel ?directorLabel ?year 
           (GROUP_CONCAT(DISTINCT ?actorLabel; separator="|") AS ?actors)
           (GROUP_CONCAT(DISTINCT ?genreLabel; separator="|") AS ?genres)
    WHERE {{
      ?movie wdt:P345 "{imdb_id}".
      ?movie wdt:P57 ?director.
      ?director rdfs:label ?directorLabel.
      
      OPTIONAL {{ ?movie wdt:P161 ?actor. ?actor rdfs:label ?actorLabel. FILTER(LANG(?actorLabel) = "en") }}
      OPTIONAL {{ ?movie wdt:P136 ?genre. ?genre rdfs:label ?genreLabel. FILTER(LANG(?genreLabel) = "en") }}
      
      OPTIONAL {{ ?movie wdt:P577 ?date. BIND(YEAR(?date) AS ?year) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
      FILTER(LANG(?directorLabel) = "en")
    }}
    GROUP BY ?movie ?movieLabel ?directorLabel ?year
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

        # We keep the "min year" logic here too just in case
        for item in raw_data['results']['bindings']:
            movie_label = item['movieLabel']['value']
            m_uri = URIRef(CINE[clean_uri_slug(movie_label)])

            g.add((m_uri, RDF.type, CINE.Film))
            g.add((m_uri, RDFS.label, Literal(movie_label)))
            g.add((m_uri, CINE.imdbId, Literal(imdb_id)))

            if 'year' in item:
                g.add((m_uri, CINE.releaseYear, Literal(int(item['year']['value']), datatype=XSD.integer)))

            d_name = item['directorLabel']['value']
            d_uri = URIRef(CINE[clean_uri_slug(d_name)])
            g.add((m_uri, CINE.directedBy, d_uri))
            g.add((d_uri, RDF.type, CINE.Person))
            g.add((d_uri, RDFS.label, Literal(d_name)))

            if 'actors' in item and item['actors']['value']:
                for a_name in item['actors']['value'].split('|')[:10]:
                    a_uri = URIRef(CINE[clean_uri_slug(a_name)])
                    g.add((m_uri, CINE.hasActor, a_uri))
                    g.add((a_uri, RDF.type, CINE.Person))
                    g.add((a_uri, RDFS.label, Literal(a_name)))

            if 'genres' in item and item['genres']['value']:
                for g_name in item['genres']['value'].split('|'):
                    g_uri = URIRef(CINE[clean_uri_slug(g_name)])
                    g.add((m_uri, CINE.hasGenre, g_uri))
                    g.add((g_uri, RDF.type, CINE.Genre))
                    g.add((g_uri, RDFS.label, Literal(g_name)))

        time.sleep(random.uniform(0.6, 1.2))
    return g

def expand_by_directors(session, g):
    print("\nStarting Phase 2: Semantic Expansion...")
    directors = list(set(g.objects(None, CINE.directedBy)))
    
    for d_uri in directors:
        d_name = str(g.value(d_uri, RDFS.label))
        print(f"Expanding: {d_name}")

        query = f"""
        SELECT ?movie ?movieLabel ?year ?imdbId 
               (GROUP_CONCAT(DISTINCT ?actorLabel; separator="|") AS ?actors)
               (GROUP_CONCAT(DISTINCT ?genreLabel; separator="|") AS ?genres)
        WHERE {{
          ?movie wdt:P57 ?dir .
          ?dir rdfs:label "{d_name}"@en .
          ?movie wdt:P345 ?imdbId .
          ?movie wdt:P31 wd:Q11424 . 
          OPTIONAL {{ ?movie wdt:P161 ?actor. ?actor rdfs:label ?actorLabel. FILTER(LANG(?actorLabel) = "en") }}
          OPTIONAL {{ ?movie wdt:P136 ?genre. ?genre rdfs:label ?genreLabel. FILTER(LANG(?genreLabel) = "en") }}
          OPTIONAL {{ ?movie wdt:P577 ?date. BIND(YEAR(?date) AS ?year) }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        GROUP BY ?movie ?movieLabel ?year ?imdbId
        """
        try:
            response = session.get(WD_ENDPOINT, params={'query': query, 'format': 'json'}, headers=get_stealth_headers())
            data = response.json()
            
            # SKEPTIC'S CACHE: Prevents the "multiple years" bug
            movie_cache = {}

            for res in data['results']['bindings']:
                m_label = res['movieLabel']['value']
                m_uri = URIRef(CINE[clean_uri_slug(m_label)])
                
                if m_uri not in movie_cache:
                    movie_cache[m_uri] = {
                        'label': m_label,
                        'imdb': res.get('imdbId', {}).get('value'),
                        'years': set(),
                        'actors': res.get('actors', {}).get('value', '').split('|'),
                        'genres': res.get('genres', {}).get('value', '').split('|')
                    }
                
                if 'year' in res:
                    movie_cache[m_uri]['years'].add(int(res['year']['value']))

            # Write clean records to graph
            for m_uri, info in movie_cache.items():
                g.add((m_uri, RDF.type, CINE.Film))
                g.add((m_uri, RDFS.label, Literal(info['label'])))
                g.add((m_uri, CINE.directedBy, d_uri))
                
                if info['imdb']: g.add((m_uri, CINE.imdbId, Literal(info['imdb'])))
                
                # FIXED: Force only the earliest year
                if info['years']:
                    g.add((m_uri, CINE.releaseYear, Literal(min(info['years']), datatype=XSD.integer)))

                for a_name in info['actors'][:10]:
                    if a_name:
                        a_uri = URIRef(CINE[clean_uri_slug(a_name)])
                        g.add((m_uri, CINE.hasActor, a_uri))
                        g.add((a_uri, RDF.type, CINE.Person))
                        g.add((a_uri, RDFS.label, Literal(a_name)))

                for g_name in info['genres']:
                    if g_name:
                        g_uri = URIRef(CINE[clean_uri_slug(g_name)])
                        g.add((m_uri, CINE.hasGenre, g_uri))
                        g.add((g_uri, RDF.type, CINE.Genre))
                        g.add((g_uri, RDFS.label, Literal(g_name)))

            time.sleep(0.8) 
        except Exception as e:
            print(f" ❌ Failed to expand {d_name}: {e}")
    return g

if __name__ == "__main__":
    session = requests.Session()
    first_graph = build_graph("imdb_100.csv")
    final_graph = expand_by_directors(session, first_graph)
    final_graph.serialize(destination="ontology/output_graph.ttl", format="turtle")
    print(f"✅ Final Graph Size: {len(final_graph)} triples.")