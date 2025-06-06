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
- `query` (required) - Search term
- `sort_by` - popularity, vote_average, vote_count
- `original_language` - Filter by language (e.g., en, fr)
- `primary_release_year` - Filter by year
- `language` - Response language
- `page` - Page number

**Example:**
```bash
curl -H "Authorization: Bearer mk_QazOTWqVXeEXWKhg7La_BlZJ0vtw0CCu0gZfIk-tE5o" \
  "http://localhost:7700/api/movies/search?query=outrun&sort_by=popularity&original_language=en"
```

**Response:**
```json
{
    "page": 1,
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
            "poster_path": "/t4pMTcnlqhaypvzJBUwTfwwcYjs.jpg",
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

### 3. Get Movie Details + Recommendations

**Endpoint:** `GET /api/movies/{movie_id}`

**Headers:**
```
Authorization: Bearer {api_key or admin001}
```

**Example:**
```bash
curl -H "Authorization: Bearer mk_QazOTWqVXeEXWKhg7La_BlZJ0vtw0CCu0gZfIk-tE5o" \
  "http://localhost:7700/api/movies/785542"
```

**Response:**
```json
{
    "cache_hit": true,
    "movie": {
        "id": 785542,
        "overview": "Fresh out of rehab, Rona returns to the Orkney Islands...",
        "poster_path": "/zfRR2CkbvYrLuOPQFm8vBaENyMy.jpg",
        "release_date": "2024-09-27",
        "title": "The Outrun",
        "vote_average": 6.808
    },
    "recommendations": [
        {
            "id": 15436,
            "title": "Let It Rain",
            "overview": "Agathe Villanova is a self-centered...",
            "poster_path": "/yg6CvMBpzz2wdnlUgB3Fhw4fKvP.jpg",
            "release_date": "2008-09-17",
            "vote_average": 5.6
        }
    ]
}
```

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
