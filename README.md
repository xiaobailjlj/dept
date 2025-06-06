# Movie API

A simple Flask-based movie search API with caching and authentication.

## Quick Start

### Docker
```bash
# Clone the repository
git clone https://github.com/xiaobailjlj/dept.git
cd dept

# Start the application
cd docker/
docker-compose up --build

# Access the application
# Frontend: http://127.0.0.1:7700
# API: http://127.0.0.1:7700/api
```

### Local Development
```bash
# Clone the repository
git clone https://github.com/xiaobailjlj/dept.git
cd dept

# Install dependencies
pip install -r requirements.txt

# Start Redis
redis-server ./conf/redis.conf
redis-cli -a "tmdb-cache-key" ping

# Run application
python app.py

# Access the application
# Frontend: http://localhost:7700
# API: http://localhost:7700/api
```

## Tech Stack

- **Backend**: Python + Flask
- **Frontend**: simple HTML
- **Database**: SQLAlchemy + SQLite
- **Cache**: Redis
- **Authentication**: Bearer Token
- **External API**: TMDB (The Movie Database)

## Features

- **Movie Search** - Search movies by text and with filters
- **Movie Details** - Get detailed info + recommendations for a specific movie
- **Redis Caching** - Fast response times
- **API Key Management** - User authentication system
- **Web Interface** - Built-in frontend

## API Authentication

### Admin Operations
Use admin key: `admin001`

### Client API Keys
1. Create user api key via admin endpoint
2. Use generated API key for movie endpoints

## Configuration

The application uses YAML configuration files:

- `conf/config.yaml` - Local development settings
- `conf/config-docker.yaml` - Docker deployment settings

## API Documentation

### 1. Create API Client

**Endpoint:** `POST /admin/clients`

**Headers:**
```
Authorization: Bearer admin001
Content-Type: application/json
```

**Request:**
```json
{
    "name": "jing",
    "email": "jing@gmail.com"
}
```

**Response:**
```json
{
    "api_key": "mk_QazOTWqVXeEXWKhg7La_BlZJ0vtw0CCu0gZfIk-tE5o",
    "email": "jing@gmail.com",
    "id": 1,
    "name": "jing"
}
```

### 2. Search Movies

**Endpoint:** `GET /api/movies/search`

**Headers:**
```
Authorization: Bearer {api_key or admin001}
```

**Parameters:**
- `query` (required) - Search term (cannot be empty)
- `include_adult` - default: false
- `language` - default: en
- `primary_release_year`
- `year`
- `region`
- `page` - default: 1
- `original_language` - Filter by original language 
- `sort_by` - Sort results by: popularity, vote_average, vote_count, default: popularity)

**Example:**
```bash
curl -H "Authorization: Bearer mk_QazOTWqVXeEXWKhg7La_BlZJ0vtw0CCu0gZfIk-tE5o" \
  "http://localhost:7700/api/movies/search?query=outrun&sort_by=vote_average&original_language=en&page=1"
```

**Response:**
```json
{
    "page": 1,
    "page_results": 1,
    "results": [
        {
            "adult": false,
            "backdrop_path": "/56Y8AVpMICNWaD6MV0wyMjCUWea.jpg",
            "genre_ids": [80, 53],
            "id": 1270097,
            "original_language": "en",
            "original_title": "Outrun",
            "overview": "After a tragic kidnapping leaves him broken...",
            "popularity": 0.2188,
            "poster_path": "/t4pMTcnlqhaypvzJBUwTfwcYjs.jpg",
            "release_date": "2021-05-28",
            "title": "Outrun",
            "vote_average": 0.0,
            "vote_count": 0
        }
    ],
    "total_pages": 1,
    "total_results": 8
}
```

**Notes:**
- Results are filtered by `original_language` if specified
- Results are sorted by the `sort_by`, default popularity
- The `page_results` field shows the number of results after filtering

### 3. Get Movie Details + Recommendations

**Endpoint:** `GET /api/movies/{movie_id}`

**Headers:**
```
Authorization: Bearer {api_key or admin001}
```

**Parameters:**
- `movie_id` (path parameter) - Must be a positive integer
- `language`
- `page`

**Example:**
```bash
curl -H "Authorization: Bearer mk_QazOTWqVXeEXWKhg7La_BlZJ0vtw0CCu0gZfIk-tE5o" \
  "http://localhost:7700/api/movies/785542?language=en-US&page=1"
```

**Response:**
```json
{
    "cache_hit": false,
    "movie": {
        "id": 785542,
        "title": "The Outrun",
        "release_date": "2024-09-27",
        "overview": "Fresh out of rehab, Rona returns to the Orkney Islands...",
        "genres": [
            {
                "id": 18,
                "name": "Drama"
            }
        ],
        "runtime": 118,
        "vote_average": 6.808,
        "vote_count": 146,
        "poster_path": "/zfRR2CkbvYrLuOPQFm8vBaENyMy.jpg",
        "backdrop_path": "/9V9pd05xDpPdEDwCqLuHkgcYmqP.jpg",
        "tagline": "Sometimes we must go back to move forward."
    },
    "recommendations": {
        "results": [
            {
                "id": 15436,
                "title": "Let It Rain",
                "release_date": "2008-09-17",
                "overview": "Agathe Villanova is a self-centered...",
                "vote_average": 5.6,
                "vote_count": 25,
                "poster_path": "/yg6CvMBpzz2wdnlUgB3Fhw4fKvP.jpg"
            }
        ],
        "total_results": 5
    }
}
```

**Notes:**
- The `cache_hit` field indicates if the response came from cache
- Cache key format: `movie:{movie_id}:{language}`

### Common Error Responses

**401 Unauthorized** - Invalid or missing API key:
```json
{
    "error": "Invalid API key"
}
```

**400 Bad Request** - Missing or invalid parameters:
```json
{
    "error": "Query parameter is required and cannot be empty"
}
```

**500 Internal Server Error** - External API or server issues:
```json
{
    "error": "API request failed with status 429"
}
```

### Status Codes
- `200` - Success
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (authentication required)
- `500` - Internal Server Error (API failures, timeouts)

## TODO

- use environment variables for sensitive data (api key for TMDB)
- safe error messages (no sensitive info leaked)
- SSL certificate verification: nginx
