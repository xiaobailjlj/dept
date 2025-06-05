from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
import requests
import os
import yaml
import logging

from cache.RedisCache import RedisCache
from auth.UserAuth import UserAuth


# init config
def load_config(config_file=''):
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except (FileNotFoundError, yaml.YAMLError) as e:
        raise Exception(f"Config error: {e}")

if os.getenv('DOCKER_ENV'):
    config_file = './conf/config_docker.yaml'
else:
    config_file = './conf/config.yaml'

config = load_config(config_file)

# init logger
logging.basicConfig(level=getattr(logging, config['logging']['level']))
logger = logging.getLogger(__name__)

# init app
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///api_keys.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app,
     resources=config['cors']['resources'],
     methods=config['cors']['methods'])

# constants
TMDB_ACCESS_TOKEN = config['security']['access_token']
TMDB_API_KEY = config['security']['api_key']
TMDB_BASE_URL = config['api']['tmdb']['base_url']
ADMIN_API_KEY = config['security']['admin_key']
TTL = config['cache']['ttl']

# init authentication manager
auth = UserAuth(app, admin_key=ADMIN_API_KEY, logger=logger)

# init cache
if config['cache']['enabled']:
    try:
        cache = RedisCache(
            host=config['cache']['host'],
            port=config['cache']['port'],
            password=config['cache']['password'],
            logger=logger
        )
    except Exception as e:
        logger.error(f"Cache initialization failed: {e}")
        cache = None
else:
    cache = None


@app.route('/admin/clients', methods=['POST'])
@auth.validate_admin
def create_client():
    data = request.json
    if not data or not data.get('name') or not data.get('email'):
        return auth.error_response('Name and email required', 400)

    try:
        client = auth.create_client(
            name=data['name'],
            email=data['email']
        )
        return jsonify(client.to_dict()), 201
    except ValueError as e:
        return auth.error_response(str(e), 400)


def error_response(message, status_code=400):
    return jsonify({'error': message}), status_code

def request_tmdb_get(path, params=None):
    if not TMDB_ACCESS_TOKEN or TMDB_ACCESS_TOKEN == 'your-tmdb-access-token':
        raise Exception("TMDB Access Token not configured")

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}"
    }
    url = f"{TMDB_BASE_URL}{path}"
    logger.debug(f"Requesting TMDB API: {url} with params: {params}")

    try:
        response = requests.get(url=url, params=params or {}, headers=headers, timeout=10)
        # logger.debug(f"TMDB API response: {response.status_code} - {response.text}")

        if response.status_code != 200:
            raise Exception(f"API request failed with status {response.status_code}")
        return response.json()

    except requests.Timeout:
        raise Exception("API request timed out")
    except requests.ConnectionError:
        raise Exception("Cannot connect to TMDB API")
    except requests.RequestException:
        raise Exception("API request failed")


@app.route('/')
def serve_frontend():
    return send_from_directory('static', 'index.html')


@app.route('/api/movies/search', methods=['GET'])
@auth.validate_api
def search_movies():
    try:
        # Validate required query parameter
        query = request.args.get('query', '').strip()
        if not query:
            return error_response('Query parameter is required and cannot be empty', 400)

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
        sort_by = request.args.get('sort_by', 'popularity')  # Default sort by popularity

        # Validate sort parameter
        valid_sort_options = ['popularity', 'vote_average', 'vote_count']
        if sort_by not in valid_sort_options:
            return error_response(f"sort_by must be one of: {', '.join(valid_sort_options)}", 400)

        # Make API request
        query_path = config['api']['tmdb']['endpoints']['search']
        data = request_tmdb_get(query_path, params)
        results = data.get('results', [])

        # Apply filters
        if original_language:
            results = [r for r in results if r.get('original_language') == original_language]

        # Sort results
        if sort_by == 'popularity':
            results.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        elif sort_by == 'vote_average':
            results.sort(key=lambda x: x.get('vote_average', 0), reverse=True)
        elif sort_by == 'vote_count':
            results.sort(key=lambda x: x.get('vote_count', 0), reverse=True)

        # Update response data
        data['results'] = results
        data['page_results'] = len(results)

        return jsonify(data), 200

    except Exception as e:
        logger.error(f"Error in search_movies: {str(e)}")
        return error_response(str(e), 500)


def extract_movie_fields(movie_data):
    """Extract essential movie fields"""
    if not movie_data:
        return {'error': 'Movie not found'}

    return {
        'id': movie_data.get('id'),
        'title': movie_data.get('title'),
        'release_date': movie_data.get('release_date'),
        'overview': movie_data.get('overview'),
        'genres': movie_data.get('genres', []),
        'runtime': movie_data.get('runtime'),
        'vote_average': movie_data.get('vote_average'),
        'vote_count': movie_data.get('vote_count'),
        'poster_path': movie_data.get('poster_path'),
        'backdrop_path': movie_data.get('backdrop_path'),
        'tagline': movie_data.get('tagline')
    }


def extract_recommendation_fields(rec_data):
    """Extract essential recommendation fields and limit to 5"""
    if not rec_data:
        return {'error': 'Recommendations not found'}

    results = rec_data.get('results', [])[:5]
    filtered_results = [
        {
            'id': movie.get('id'),
            'title': movie.get('title'),
            'release_date': movie.get('release_date'),
            'overview': movie.get('overview'),
            'vote_average': movie.get('vote_average'),
            'vote_count': movie.get('vote_count'),
            'poster_path': movie.get('poster_path')
        }
        for movie in results
    ]

    return {
        'results': filtered_results,
        'total_results': len(filtered_results)
    }

@app.route('/api/movies/<int:movie_id>', methods=['GET'])
@auth.validate_api
def get_movie(movie_id):
    try:
        # Validate movie_id
        if movie_id <= 0:
            return error_response('Movie ID must be a positive integer', 400)

        language = request.args.get('language', 'en-US')
        page = request.args.get('page', '1')
        cache_key = f"movie:{movie_id}:{language}"

        # Try cache
        if cache:
            cached = cache.get(cache_key)
            if cached:
                cached['cache_hit'] = True
                return jsonify(cached), 200

        # Get movie details
        try:
            details_path = config['api']['tmdb']['endpoints']['details'].format(movie_id=movie_id)
            details_params = {'language': language}
            movie_data = request_tmdb_get(details_path, details_params)
        except Exception as e:
            logger.error(f"Failed to fetch movie details for ID {movie_id}: {str(e)}")
            return error_response(f"{str(e)}", 500)

        # Get recommendations
        try:
            recommendations_path = config['api']['tmdb']['endpoints']['recommendations'].format(movie_id=movie_id)
            rec_params = {'language': language, 'page': page}
            rec_data = request_tmdb_get(recommendations_path, rec_params)
        except Exception as e:
            logger.warning(f"Failed to fetch recommendations for movie {movie_id}: {str(e)}")
            return error_response(f"{str(e)}", 500)

        # Combine responses
        result = {
            'movie': extract_movie_fields(movie_data),
            'recommendations': extract_recommendation_fields(rec_data),
            'cache_hit': False
        }

        # Cache result
        if cache:
            cache.set(cache_key, result, TTL)

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in get_movie_with_recommendations: {str(e)}")
        return error_response(str(e), 500)


@app.route('/api/cache/clear', methods=['POST'])
@auth.validate_admin
def clear_cache():
    if cache and cache.clear_all():
        return jsonify({'message': 'Cache cleared'}), 200
    return jsonify({'message': 'Cache not available'}), 200


if __name__ == '__main__':
    # Create tables
    with app.app_context():
        auth.db.create_all()
        logger.info("Database ready")

    # Run app
    server_config = config['server']
    app.run(
        debug=server_config['debug'],
        host=server_config['host'],
        port=server_config['port']
    )