from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import yaml
import logging

def load_config(config_file='./conf/config.yaml'):
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    with open(config_path, 'r') as file:
        return yaml.safe_load(file)


config = load_config()

logging.basicConfig(level=getattr(logging, config['logging']['level']))  # INFO, DEBUG, WARNING, ERROR, CRITICAL
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app,
     resources=config['cors']['resources'],
     methods=config['cors']['methods'])

TMDB_ACCESS_TOKEN = config['security']['access_token']
TMDB_API_KEY = config['security']['api_key']
TMDB_BASE_URL = config['api']['tmdb']['base_url']


def request_tmdb_get(path, params):
    """Make GET request to TMDB API and return raw response data"""
    if not TMDB_ACCESS_TOKEN or TMDB_ACCESS_TOKEN == 'your-tmdb-access-token':
        raise ValueError("TMDb Access Token not configured")

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}"
    }
    url = f"{TMDB_BASE_URL}{path}"
    logging.debug(f"Requesting TMDB API: {url} with params: {params}")

    response = requests.get(url=url, params=params, headers=headers)
    return response.json(), response.status_code


@app.route('/api/movies/search', methods=['GET'])
def search_movies():
    """Search for movies using TMDB API with enhanced filtering and sorting"""

    # Validate required query parameter
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query parameter is required and cannot be empty'}), 400

    # Build TMDB API parameters
    params = {
        'query': query,
        'include_adult': request.args.get('include_adult', 'false'),
        'language': request.args.get('language', 'en'),
        'primary_release_year': request.args.get('primary_release_year'),
        'year': request.args.get('year'),
        'region': request.args.get('region'),
        'page': request.args.get('page', '1'),
    }
    params = {k: v for k, v in params.items() if v not in (None, '')}

    # Get filter and sort parameters
    original_language = request.args.get('original_language')
    sort_by = request.args.get('sort_by', 'popularity')  # default to popularity
    min_vote_count = request.args.get('min_vote_count', type=int)

    try:
        query_path = config['api']['tmdb']['endpoints']['search']
        data, status_code = request_tmdb_get(query_path, params)

        if status_code != 200:
            return jsonify({'error': 'Failed to fetch data from TMDB API'}), status_code

        results = data.get('results', [])

        # Apply filters
        if original_language:
            results = [r for r in results if r.get('original_language') == original_language]

        if min_vote_count:
            results = [r for r in results if r.get('vote_count', 0) >= min_vote_count]

        # Sort results
        sort_key_map = {
            'popularity': lambda x: x.get('popularity', 0),
            'vote_average': lambda x: x.get('vote_average', 0),
            'vote_count': lambda x: x.get('vote_count', 0)
        }

        if sort_by in sort_key_map:
            results.sort(key=sort_key_map[sort_by], reverse=True)

        # Update response data
        data['results'] = results
        data['total_results'] = len(results) if any([original_language, min_vote_count]) else data.get('total_results')

        return jsonify(data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# extract essential movie fields
def extract_movie_fields(movie_data):
    if 'error' in movie_data or not movie_data:
        return {'error': 'Movie not found'}
    return {
        'id': movie_data.get('id'),
        'title': movie_data.get('title'),
        'release_date': movie_data.get('release_date'),
        'overview': movie_data.get('overview'),  # plot summary
        'genres': movie_data.get('genres', []),
        'runtime': movie_data.get('runtime'),
        'vote_average': movie_data.get('vote_average'),
        'vote_count': movie_data.get('vote_count'),
        'poster_path': movie_data.get('poster_path'),
        'backdrop_path': movie_data.get('backdrop_path'),
        'tagline': movie_data.get('tagline')
    }

# extract essential recommendation fields and limit to 5
def extract_recommendation_fields(rec_data):
    if 'error' in rec_data or not rec_data:
        return {'error': 'Recommendations not found'}

    results = rec_data.get('results', [])[:5]  # limit to 5
    filtered_results = []

    for movie in results:
        filtered_results.append({
            'id': movie.get('id'),
            'title': movie.get('title'),
            'release_date': movie.get('release_date'),
            'overview': movie.get('overview'),
            'vote_average': movie.get('vote_average'),
            'vote_count': movie.get('vote_count'),
            'poster_path': movie.get('poster_path')
        })

    return {
        'results': filtered_results,
        'total_results': len(filtered_results)
    }

@app.route('/api/movies/<int:movie_id>', methods=['GET'])
def get_movie_with_recommendations(movie_id):
    """Get movie details + recommendations in single response using TMDB API"""

    # parameter check, movie_id is required
    if not movie_id or movie_id <= 0:
        return jsonify({'error': 'Movie ID is required'}), 400

    # get movie details
    details_path = config['api']['tmdb']['endpoints']['details'].format(movie_id=movie_id)
    details_params = {'language': request.args.get('language', 'en-US')}

    try:
        details_response = request_tmdb_get(details_path, details_params)
    except Exception as e:
        logger.error(f"Error fetching movie details: {str(e)}")
        return jsonify({'error': str(e)}), 500

    # get recommendations
    recommendations_path = config['api']['tmdb']['endpoints']['recommendations'].format(movie_id=movie_id)
    rec_params = {
        'language': request.args.get('language', 'en-US'),
        'page': request.args.get('page', '1')
    }

    try:
        rec_response = request_tmdb_get(recommendations_path, rec_params)
    except Exception as e:
        # if recommendations fail, still return movie details
        logger.error(f"Error fetching recommendations: {str(e)}")
        rec_response = (None, 500)

    # combine responses with extracted fields
    result = {
        'movie': extract_movie_fields(details_response[0] if details_response[1] == 200 else {}),
        'recommendations': extract_recommendation_fields(rec_response[0] if rec_response[1] == 200 else {})
    }

    return jsonify(result), 200


if __name__ == '__main__':
    if not TMDB_API_KEY or TMDB_API_KEY == 'your-tmdb-api-key':
        logging.error("TMDB API key not configured!")
    if not TMDB_ACCESS_TOKEN or TMDB_ACCESS_TOKEN == 'your-tmdb-access-token':
        logging.error("TMDB Access Token not configured!")

    server_config = config['server']
    app.run(
        debug=server_config['debug'],
        host=server_config['host'],
        port=server_config['port']
    )