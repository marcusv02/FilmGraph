import pandas as pd
import time
import random
import requests
import re
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, XSD

CINE = Namespace("http://filmgraph/ontology/")
WD_ENDPOINT = "https://query.wikidata.org/sparql"

def get_headers():
    return {
        'User-Agent': 'FilmGraphBot/1.0 Python-requests',
        'Accept': 'application/sparql-results+json'
    }

def clean_uri_slug(text):
    if not text: return "Unknown"
    clean = re.sub(r'["\'.]', '', text)
    return clean.replace(" ", "_").replace("/", "_")

def query_wikidata(session, sparql_query):
    try:
        response = session.get(WD_ENDPOINT, params={'query': sparql_query, 'format': 'json'}, headers=get_headers())
        return response.json()
    except Exception as e:
        print(f"   ❌ Query error: {e}")
        return None

def add_movie_to_graph(g, movie_label, imdb_id, year, director_name, actors, genres):
    m_uri = URIRef(CINE[clean_uri_slug(movie_label)])
    
    # Movie properties
    g.add((m_uri, RDF.type, CINE.Film))
    g.add((m_uri, RDFS.label, Literal(movie_label)))
    g.add((m_uri, CINE.imdbId, Literal(imdb_id)))
    g.add((m_uri, CINE.releaseYear, Literal(year, datatype=XSD.integer)))
    
    # Director
    d_uri = URIRef(CINE[clean_uri_slug(director_name)])
    g.add((m_uri, CINE.directedBy, d_uri))
    g.add((d_uri, RDF.type, CINE.Person))
    g.add((d_uri, RDFS.label, Literal(director_name)))
    
    # Actors
    for a_name in actors:
        a_uri = URIRef(CINE[clean_uri_slug(a_name)])
        g.add((m_uri, CINE.hasActor, a_uri))
        g.add((a_uri, RDF.type, CINE.Person))
        g.add((a_uri, RDFS.label, Literal(a_name)))
    
    # Genres
    for g_name in genres:
        g_uri = URIRef(CINE[clean_uri_slug(g_name)])
        g.add((m_uri, CINE.hasGenre, g_uri))
        g.add((g_uri, RDF.type, CINE.Genre))
        g.add((g_uri, RDFS.label, Literal(g_name)))

def process_movie_results(results):
    movies = {}
    
    for item in results:
        movie_label = item.get('movieLabel', {}).get('value')
        if not movie_label:
            continue
            
        if movie_label not in movies:
            movies[movie_label] = {
                'label': movie_label,
                'imdb_id': item.get('imdbId', {}).get('value'),
                'years': set(),
                'directors': set(),
                'actors': set(),
                'genres': set()
            }
        
        # Collect years
        if 'year' in item:
            try:
                movies[movie_label]['years'].add(int(item['year']['value']))
            except (ValueError, KeyError):
                pass
        
        # Collect director
        if 'directorLabel' in item:
            movies[movie_label]['directors'].add(item['directorLabel']['value'])
        
        # Collect actors
        if 'actors' in item and item['actors']['value'].strip():
            for a in item['actors']['value'].split('|')[:10]:
                if a.strip():
                    movies[movie_label]['actors'].add(a.strip())
        
        # Collect genres
        if 'genres' in item and item['genres']['value'].strip():
            for g in item['genres']['value'].split('|'):
                if g.strip():
                    movies[movie_label]['genres'].add(g.strip())
    
    return movies

def build_graph(csv_path):
    g = Graph()
    g.bind("cine", CINE)
    df = pd.read_csv(csv_path)
    session = requests.Session()
    processed_ids = set()

    for index, row in df.iterrows():
        imdb_id = row['imdb_title_id']
        if imdb_id in processed_ids:
            continue
            
        print(f"[{index+1}/{len(df)}] Processing {imdb_id}...")
        
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
        
        raw_data = query_wikidata(session, query)
        if not raw_data or not raw_data.get('results', {}).get('bindings'):
            continue

        # Process results
        movies = process_movie_results(raw_data['results']['bindings'])
        
        for movie_label, data in movies.items():
            # Validate minimum requirements
            if data['years'] and data['directors'] and data['actors'] and data['genres']:
                add_movie_to_graph(
                    g, 
                    movie_label,
                    imdb_id,
                    min(data['years']),
                    list(data['directors'])[0],
                    data['actors'],
                    data['genres']
                )
                print(f"✅ Added: {movie_label}")
                processed_ids.add(imdb_id)

        time.sleep(random.uniform(0.6, 1.2))
    
    return g, processed_ids

def expand_by_directors(session, g, processed_ids):
    print("\nPhase 2: Expanding by directors...")
    directors = list(set(g.objects(None, CINE.directedBy)))
    
    # Process directors in batches of 5
    batch_size = 5
    for i in range(0, len(directors), batch_size):
        batch = directors[i:i+batch_size]
        director_names = [str(g.value(d, RDFS.label)) for d in batch]
        
        print(f"Expanding batch: {', '.join(director_names)}")
        
        values = " ".join([f'("{name}"@en)' for name in director_names])
        query = f"""
        SELECT ?movie ?movieLabel ?directorLabel ?year ?imdbId 
               (GROUP_CONCAT(DISTINCT ?actorLabel; separator="|") AS ?actors)
               (GROUP_CONCAT(DISTINCT ?genreLabel; separator="|") AS ?genres)
        WHERE {{
          VALUES (?dirLabel) {{ {values} }}
          ?movie wdt:P57 ?dir.
          ?dir rdfs:label ?dirLabel.
          ?movie wdt:P345 ?imdbId.
          ?movie wdt:P31 wd:Q11424.
          ?dir rdfs:label ?directorLabel.
          OPTIONAL {{ ?movie wdt:P161 ?actor. ?actor rdfs:label ?actorLabel. FILTER(LANG(?actorLabel) = "en") }}
          OPTIONAL {{ ?movie wdt:P136 ?genre. ?genre rdfs:label ?genreLabel. FILTER(LANG(?genreLabel) = "en") }}
          OPTIONAL {{ ?movie wdt:P577 ?date. BIND(YEAR(?date) AS ?year) }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
          FILTER(LANG(?directorLabel) = "en")
        }}
        GROUP BY ?movie ?movieLabel ?directorLabel ?year ?imdbId
        """
        
        data = query_wikidata(session, query)
        if not data or not data.get('results', {}).get('bindings'):
            time.sleep(0.8)
            continue
        
        # Process batch results
        movies = process_movie_results(data['results']['bindings'])
        
        for movie_label, movie_data in movies.items():
            if (movie_data.get('imdb_id') in processed_ids or 
                not (movie_data['years'] and movie_data['directors'] and 
                     movie_data['actors'] and movie_data['genres'])):
                continue
            
            add_movie_to_graph(
                g,
                movie_label,
                movie_data['imdb_id'],
                min(movie_data['years']),
                list(movie_data['directors'])[0],
                movie_data['actors'],
                movie_data['genres']
            )
            if movie_data.get('imdb_id'):
                processed_ids.add(movie_data['imdb_id'])
        
        time.sleep(0.8)
    
    return g

if __name__ == "__main__":
    session = requests.Session()
    graph, processed = build_graph("imdb_100.csv")
    final_graph = expand_by_directors(session, graph, processed)
    final_graph.serialize(destination="ontology/output_graph.ttl", format="turtle")
    print(f"\n✅ Complete! Final graph: {len(final_graph)} triples")