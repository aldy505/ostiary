from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import os
from typing import Annotated, Union

from fastapi import BackgroundTasks, FastAPI, Header
from pydantic import BaseModel
from tinyflux import Point, TinyFlux
from tinyflux.queries import TagQuery, TimeQuery
import geoip2.database

import sentry_sdk

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    # Add data like request headers and IP for users, if applicable;
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    sample_rate=float(os.environ.get("SENTRY_SAMPLE_RATE", "1.0")),
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
    # To collect profiles for all profile sessions,
    # set `profile_session_sample_rate` to 1.0.
    profile_session_sample_rate=float(
        os.environ.get("SENTRY_PROFILE_SESSION_SAMPLE_RATE", "0.0")
    ),
    # Profiles will be automatically collected while
    # there is an active span.
    profile_lifecycle="trace",
    # Enable logs to be sent to Sentry
    enable_logs=True,
)

retention_days = int(os.environ.get("DATA_RETENTION_DAYS", "30"))

geoip_country_db_path = os.environ.get("GEOIP_COUNTRY_DB_PATH")
geoip_asn_db_path = os.environ.get("GEOIP_ASN_DB_PATH")
geoip_country_db: geoip2.database.Reader | None = None
geoip_asn_db: geoip2.database.Reader | None = None

if geoip_country_db_path:
    geoip_country_db = geoip2.database.Reader(geoip_country_db_path)

if geoip_asn_db_path:
    geoip_asn_db = geoip2.database.Reader(geoip_asn_db_path)

db = TinyFlux(os.environ.get("DATA_PATH", "requests.csv"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    db.close()
    if geoip_country_db is not None:
        geoip_country_db.close()
    if geoip_asn_db is not None:
        geoip_asn_db.close()


app = FastAPI(lifespan=lifespan)


def cleanup():
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    db.delete(TimeQuery() < cutoff_date)


class CommonHeaders(BaseModel):
    x_forwarded_for: Union[str, None] = None
    user_agent: Union[str, None] = None
    x_forwarded_host: Union[str, None] = None
    x_forwarded_port: Union[str, None] = None
    x_forwarded_proto: Union[str, None] = None
    x_forwarded_server: Union[str, None] = None
    x_forwarded_uri: Union[str, None] = None


@app.get("/api/v0/request")
def read_root(
    headers: Annotated[CommonHeaders, Header()],
    background_tasks: BackgroundTasks,
):
    if geoip_country_db is not None and headers.x_forwarded_for:
        try:
            country_response = geoip_country_db.country(headers.x_forwarded_for)
            country = country_response.country.name
        except:
            country = None

    if geoip_asn_db is not None and headers.x_forwarded_for:
        try:
            asn_response = geoip_asn_db.asn(headers.x_forwarded_for)
            asn_org = asn_response.autonomous_system_organization
            asn_number = asn_response.autonomous_system_number
        except:
            asn_org = None
            asn_number = None

    point = Point(
        time=datetime.now(timezone.utc),
        measurement="request",
        tags={
            "user_agent": headers.user_agent or "unknown",
            "ip_address": headers.x_forwarded_for or "unknown",
            "forwarded_host": headers.x_forwarded_host or "unknown",
            "forwarded_port": headers.x_forwarded_port or "unknown",
            "forwarded_proto": headers.x_forwarded_proto or "unknown",
            "forwarded_server": headers.x_forwarded_server or "unknown",
            "forwarded_uri": headers.x_forwarded_uri or "unknown",
            "geoip_country": country,
            "geoip_asn_org": asn_org,
            "geoip_asn_number": "AS" + str(asn_number)
            if asn_number is not None
            else None,
        },
        fields={"count": 1},
    )

    try:
        db.insert(point)
    except OSError as os_error:
        sentry_sdk.capture_exception(os_error)
    except TypeError as type_error:
        sentry_sdk.capture_exception(type_error)

    # Execute cleanup in the background randomly to avoid slowing down requests.
    if os.urandom(1)[0] < 5:  # ~2% chance
        background_tasks.add_task(cleanup)

    return "OK"


@app.get("/query")
def read_item(
    ip_address: Union[str, None] = None,
    host: Union[str, None] = None,
    method: Union[str, None] = None,
    start_date: Union[str, datetime, None] = None,
    end_date: Union[str, datetime, None] = None,
):
    # if start_date and end_date are provided, convert them to datetime objects
    if start_date and isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date)
    elif start_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(
            days=1
        )  # default to last 24 hours
    if end_date and isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date)
    elif end_date is None:
        end_date = datetime.now(timezone.utc)  # default to now

    if ip_address is None and host is None:
        points = db.search((TimeQuery() >= start_date) & (TimeQuery() <= end_date))
    elif ip_address is None and host is not None:
        points = db.search(
            (TagQuery().forwarded_host == host)
            & (TimeQuery() >= start_date)
            & (TimeQuery() <= end_date)
        )
    elif ip_address is not None and host is None:
        points = db.search(
            (TagQuery().ip_address == ip_address)
            & (TimeQuery() >= start_date)
            & (TimeQuery() <= end_date)
        )
    else:
        points = db.search(
            (TagQuery().ip_address == ip_address)
            & (TagQuery().forwarded_host == host)
            & (TimeQuery() >= start_date)
            & (TimeQuery() <= end_date)
        )

    # Group points by IP address
    grouped: dict[str, list[dict[str, str]]] = {}
    for point in points:
        ip = point.tags.get("ip_address", "unknown")
        if ip not in grouped:
            grouped[ip] = []

        grouped[ip].append(
            {
                "time": point.time.isoformat(),
                "user_agent": point.tags.get("user_agent", "unknown"),
                "host": point.tags.get("forwarded_host", "unknown"),
                "path": point.tags.get("forwarded_uri", "unknown"),
                "country": point.tags.get("geoip_country"),
                "asn_org": point.tags.get("geoip_asn_org"),
                "asn_number": point.tags.get("geoip_asn_number"),
            }
        )

    # Convert to list format
    return [
        {"ip_address": ip, "hits": len(points_list), "points": points_list}
        for ip, points_list in grouped.items()
    ]
