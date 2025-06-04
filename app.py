from cache.RedisCache import RedisCache
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
import requests
import os
import yaml
import logging

# Import auth class
from auth.UserAuth import UserAuth


# init config
def load_config(config_file='./conf/config.yaml'):
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except (FileNotFoundError, yaml.YAMLError) as e:
        raise Exception(f"Config error: {e}")


config = load_config()

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


def request_tmdb_get(path, params=None):
    if not TMDB_ACCESS_TOKEN or TMDB_ACCESS_TOKEN == 'your-tmdb-access-token':
        raise Exception("TMDB Access Token not configured")

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TMDB_ACCESS_TOKEN}"
    }
    url = f"{TMDB_BASE_URL}{path}"
    logger.info(f"Requesting TMDB API: {url}")

    try:
        response = requests.get(url=url, params=params or {}, headers=headers, timeout=10)
        if response.status_code != 200:
            raise Exception(f"API request failed with status {response.status_code}")
        return response.json()
    except requests.Timeout:
        raise Exception("API request timed out")
    except requests.ConnectionError:
        raise Exception("Cannot connect to TMDB API")

@app.route('/')
def serve_frontend():
    return send_from_directory('static', 'index.html')


@app.route('/api/movies/search', methods=['GET'])
@auth.validate_api
def search_movies():
    query = request.args.get('query', '').strip()
    if not query:
        return auth.error_response('Query parameter required', 400)

    params = {
        'query': query,
        'language': request.args.get('language', 'en'),
        'page': request.args.get('page', '1'),
    }

    try:
        search_path = config['api']['tmdb']['endpoints']['search']
        data = request_tmdb_get(search_path, params)
        return jsonify(data), 200
    except Exception as e:
        return auth.error_response(str(e), 500)


@app.route('/api/movies/<int:movie_id>', methods=['GET'])
@auth.validate_api
def get_movie(movie_id):
    if movie_id <= 0:
        return auth.error_response('Invalid movie ID', 400)

    language = request.args.get('language', 'en-US')
    cache_key = f"movie:{movie_id}:{language}"

    # Try cache
    if cache:
        cached = cache.get(cache_key)
        if cached:
            cached['cache_hit'] = True
            return jsonify(cached), 200

    try:
        # Get movie details
        details_path = config['api']['tmdb']['endpoints']['details'].format(movie_id=movie_id)
        movie_data = request_tmdb_get(details_path, {'language': language})

        # Get recommendations
        rec_path = config['api']['tmdb']['endpoints']['recommendations'].format(movie_id=movie_id)
        rec_data = request_tmdb_get(rec_path, {'language': language})

        result = {
            'movie': {
                'id': movie_data.get('id'),
                'title': movie_data.get('title'),
                'overview': movie_data.get('overview'),
                'release_date': movie_data.get('release_date'),
                'vote_average': movie_data.get('vote_average'),
                'poster_path': movie_data.get('poster_path')
            },
            'recommendations': rec_data.get('results', [])[:5],
            'cache_hit': False
        }

        # Cache result
        if cache:
            cache.set(cache_key, result, TTL)

        return jsonify(result), 200

    except Exception as e:
        return auth.error_response(str(e), 500)


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