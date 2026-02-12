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

def add_film_to_graph(g, film_label, imdb_id, year, duration, director_name, actors, genres):
    f_uri = URIRef(CINE[clean_uri_slug(film_label)])
    
    # Film properties
    g.add((f_uri, RDF.type, CINE.Film))
    g.add((f_uri, RDFS.label, Literal(film_label)))
    g.add((f_uri, CINE.imdbId, Literal(imdb_id)))
    g.add((f_uri, CINE.year, Literal(year, datatype=XSD.integer)))
    g.add((f_uri, CINE.duration, Literal(duration, datatype=XSD.integer)))
    
    # Director
    d_uri = URIRef(CINE[clean_uri_slug(director_name)])
    g.add((f_uri, CINE.directedBy, d_uri))
    g.add((d_uri, RDF.type, CINE.Person))
    g.add((d_uri, RDFS.label, Literal(director_name)))
    
    # Actors
    for a_name in actors:
        a_uri = URIRef(CINE[clean_uri_slug(a_name)])
        g.add((f_uri, CINE.hasActor, a_uri))
        g.add((a_uri, RDF.type, CINE.Person))
        g.add((a_uri, RDFS.label, Literal(a_name)))
    
    # Genres
    for g_name in genres:
        g_uri = URIRef(CINE[clean_uri_slug(g_name)])
        g.add((f_uri, CINE.hasGenre, g_uri))
        g.add((g_uri, RDF.type, CINE.Genre))
        g.add((g_uri, RDFS.label, Literal(g_name)))

def process_film_results(results):
    films = {}
    
    for item in results:
        film_label = item.get('filmLabel', {}).get('value')
        if not film_label:
            continue
            
        if film_label not in films:
            films[film_label] = {
                'label': film_label,
                'imdb_id': item.get('imdbId', {}).get('value'),
                'years': set(),
                'duration': 0,
                'directors': set(),
                'actors': set(),
                'genres': set()
            }
        
        if 'year' in item:
            try:
                films[film_label]['years'].add(int(item['year']['value']))
            except (ValueError, KeyError):
                pass

        if 'duration' in item:
            try:
                # Wikidata duration is in minutes
                films[film_label]['duration'] = int(float(item['duration']['value']))
            except (ValueError, KeyError):
                pass
        
        if 'directorLabel' in item:
            films[film_label]['directors'].add(item['directorLabel']['value'])
        
        if 'actors' in item and item['actors']['value'].strip():
            for a in item['actors']['value'].split('|')[:10]:
                if a.strip():
                    films[film_label]['actors'].add(a.strip())
        
        if 'genres' in item and item['genres']['value'].strip():
            for g in item['genres']['value'].split('|'):
                if g.strip():
                    films[film_label]['genres'].add(g.strip())
    
    return films

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
        SELECT ?film ?filmLabel ?directorLabel ?year ?duration
               (GROUP_CONCAT(DISTINCT ?actorLabel; separator="|") AS ?actors)
               (GROUP_CONCAT(DISTINCT ?genreLabel; separator="|") AS ?genres)
        WHERE {{
          ?film wdt:P345 "{imdb_id}".
          ?film wdt:P57 ?director.
          ?director rdfs:label ?directorLabel.
          OPTIONAL {{ ?film wdt:P161 ?actor. ?actor rdfs:label ?actorLabel. FILTER(LANG(?actorLabel) = "en") }}
          OPTIONAL {{ ?film wdt:P136 ?genre. ?genre rdfs:label ?genreLabel. FILTER(LANG(?genreLabel) = "en") }}
          OPTIONAL {{ ?film wdt:P577 ?date. BIND(YEAR(?date) AS ?year) }}
          OPTIONAL {{ ?film wdt:P2047 ?duration. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
          FILTER(LANG(?directorLabel) = "en")
        }}
        GROUP BY ?film ?filmLabel ?directorLabel ?year ?duration
        """
        
        raw_data = query_wikidata(session, query)
        if not raw_data or not raw_data.get('results', {}).get('bindings'):
            continue

        # Process results
        films = process_film_results(raw_data['results']['bindings'])
        
        for film_label, data in films.items():
            # Validate minimum requirements
            if data['years'] and data['duration'] and data['directors'] and data['actors'] and data['genres']:
                add_film_to_graph(
                    g, 
                    film_label,
                    imdb_id,
                    min(data['years']),
                    data['duration'],
                    list(data['directors'])[0],
                    data['actors'],
                    data['genres']
                )
                print(f"✅ Added: {film_label}")
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
        SELECT ?film ?filmLabel ?directorLabel ?year ?duration ?imdbId 
               (GROUP_CONCAT(DISTINCT ?actorLabel; separator="|") AS ?actors)
               (GROUP_CONCAT(DISTINCT ?genreLabel; separator="|") AS ?genres)
        WHERE {{
          VALUES (?dirLabel) {{ {values} }}
          ?film wdt:P57 ?dir.
          ?dir rdfs:label ?dirLabel.
          ?film wdt:P345 ?imdbId.
          ?film wdt:P31 wd:Q11424.
          ?dir rdfs:label ?directorLabel.
          OPTIONAL {{ ?film wdt:P161 ?actor. ?actor rdfs:label ?actorLabel. FILTER(LANG(?actorLabel) = "en") }}
          OPTIONAL {{ ?film wdt:P136 ?genre. ?genre rdfs:label ?genreLabel. FILTER(LANG(?genreLabel) = "en") }}
          OPTIONAL {{ ?film wdt:P577 ?date. BIND(YEAR(?date) AS ?year) }}
          OPTIONAL {{ ?film wdt:P2047 ?duration. }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
          FILTER(LANG(?directorLabel) = "en")
        }}
        GROUP BY ?film ?filmLabel ?directorLabel ?year ?duration ?imdbId
        """
        
        data = query_wikidata(session, query)
        if not data or not data.get('results', {}).get('bindings'):
            time.sleep(0.8)
            continue
        
        # Process batch results
        films = process_film_results(data['results']['bindings'])
        
        for film_label, film_data in films.items():
            if (film_data.get('imdb_id') in processed_ids or 
                not (film_data['years'] and film_data['duration'] and film_data['directors'] and 
                     film_data['actors'] and film_data['genres'])):
                continue
            
            add_film_to_graph(
                g,
                film_label,
                film_data['imdb_id'],
                min(film_data['years']),
                film_data['duration'],
                list(film_data['directors'])[0],
                film_data['actors'],
                film_data['genres']
            )
            if film_data.get('imdb_id'):
                processed_ids.add(film_data['imdb_id'])
        
        time.sleep(0.8)
    
    return g

if __name__ == "__main__":
    session = requests.Session()
    graph, processed = build_graph("imdb_100.csv")
    final_graph = expand_by_directors(session, graph, processed)
    final_graph.serialize(destination="ontology/output_graph.ttl", format="turtle")
    print(f"\n✅ Complete! Final graph: {len(final_graph)} triples")