# Ostiary

A lightweight request logging service designed to work with Traefik or Caddy's Forward Auth middleware. Ostiary captures and stores HTTP request metadata with optional GeoIP enrichment for analytics and monitoring.

## Features

- **Forward Auth Integration**: Seamlessly integrates with Traefik or Caddy as a forward authentication middleware
- **GeoIP Enrichment**: Optional IP geolocation and ASN information using MaxMind GeoLite2 databases
- **Request Analytics**: Query and analyze requests by IP address, host, and time range
- **Sentry Integration**: Built-in error tracking and performance monitoring
- **Lightweight**: Built with FastAPI and TinyFlux for minimal resource usage

## Endpoints

### `GET /api/v0/request`
Forward auth endpoint that logs request metadata. Returns `OK` for all requests.

**Headers** (automatically forwarded by Traefik/Caddy):
- `x-forwarded-for`: Client IP address
- `x-forwarded-host`: Original host
- `x-forwarded-port`: Original port
- `x-forwarded-proto`: Protocol (http/https)
- `x-forwarded-server`: Server name
- `x-forwarded-uri`: Request URI
- `user-agent`: Client user agent

### `GET /query`
Query logged requests with optional filters.

**Query Parameters**:
- `ip_address` (optional): Filter by IP address
- `host` (optional): Filter by forwarded host
- `start_date` (optional): Start date in ISO format (default: 24 hours ago)
- `end_date` (optional): End date in ISO format (default: now)

**Response**:
```json
[
  {
    "ip_address": "127.0.0.1",
    "hits": 1,
    "points": [
      {
        "time": "2026-01-31T02:15:50.058539+00:00",
        "user_agent": "Mozilla/5.0...",
        "host": "example.com",
        "path": "/api/endpoint",
        "country": "United States",
        "asn_org": "Microsoft Corporation",
        "asn_number": "AS..."
      }
    ]
  }
]
```

## Setup

### Docker Compose with Traefik

```yaml
services:
  ostiary:
    image: ghcr.io/aldy505/ostiary:latest
    networks:
      - public-web
    environment:
      # Optional: GeoIP database paths
      GEOIP_COUNTRY_DB_PATH: /geoip/GeoLite2-Country.mmdb
      GEOIP_ASN_DB_PATH: /geoip/GeoLite2-ASN.mmdb
      # Data storage path
      DATA_PATH: /data/request.csv
      # Optional: Sentry configuration
      SENTRY_DSN: your-sentry-dsn
      SENTRY_SAMPLE_RATE: "1.0"
      SENTRY_TRACES_SAMPLE_RATE: "0.0"
      SENTRY_PROFILE_SESSION_SAMPLE_RATE: "0.0"
    volumes:
      - geoip-db:/geoip/
      - ostiary-data:/data/

  # Optional: Keep GeoIP databases updated
  geoipupdate:
    image: ghcr.io/maxmind/geoipupdate:v7.1.1
    environment:
      GEOIPUPDATE_EDITION_IDS: GeoLite2-Country GeoLite2-ASN
      GEOIPUPDATE_ACCOUNT_ID: your-account-id
      GEOIPUPDATE_LICENSE_KEY: your-license-key
      GEOIPUPDATE_VERBOSE: 1
    volumes:
      - geoip-db:/usr/share/GeoIP

volumes:
  geoip-db:
  ostiary-data:

networks:
  public-web:
    external: true
```

### Traefik Forward Auth Configuration

Add these labels to the services you want to protect/monitor:

```yaml
labels:
  - "traefik.http.middlewares.forwardauth.forwardauth.address=http://ostiary:8000/api/v0/request"
  - "traefik.http.middlewares.forwardauth.forwardauth.trustForwardHeader=true"
  # Apply the middleware to your router
  - "traefik.http.routers.myapp.middlewares=forwardauth"
```

### Caddy Forward Auth Configuration

```caddyfile
example.com {
    forward_auth ostiary:8000 {
        uri /api/v0/request
        copy_headers X-Forwarded-For X-Forwarded-Host X-Forwarded-Port X-Forwarded-Proto X-Forwarded-Server X-Forwarded-Uri User-Agent
    }
    reverse_proxy your-backend:8080
}
```

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATA_PATH` | Path to CSV file for storing requests | `requests.csv` | No |
| `GEOIP_COUNTRY_DB_PATH` | Path to GeoLite2-Country.mmdb | - | No |
| `GEOIP_ASN_DB_PATH` | Path to GeoLite2-ASN.mmdb | - | No |
| `SENTRY_DSN` | Sentry DSN for error tracking | - | No |
| `SENTRY_SAMPLE_RATE` | Sentry error sample rate | `1.0` | No |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry trace sample rate | `0.0` | No |
| `SENTRY_PROFILE_SESSION_SAMPLE_RATE` | Sentry profile sample rate | `0.0` | No |

## GeoIP Setup

To enable GeoIP enrichment, you'll need a MaxMind account:

1. Sign up for a free account at [MaxMind](https://www.maxmind.com/en/geolite2/signup)
2. Generate a license key
3. Use the `geoipupdate` container to automatically download and update databases
4. Set `GEOIP_COUNTRY_DB_PATH` and `GEOIP_ASN_DB_PATH` environment variables

## Building

```bash
docker build -t ostiary:latest .
```

## Development

```bash
# Install dependencies
uv sync

# Run locally
fastapi dev main.py
```

## License

```
   Copyright 2026 Reinaldy Rafli <github@reinaldyrafli.com>

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```

See [LICENSE](./LICENSE)