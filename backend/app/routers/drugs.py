from typing import List, Optional
import os
import json
import ssl
import boto3
import pg8000.dbapi as pg_dbapi
from fastapi import APIRouter, Depends, HTTPException, Query, status
import traceback

from ..security import get_cognito_user_info

router = APIRouter(prefix="/drugs", tags=["Drugs"])


def _get_db_creds(secret_arn: str, region: Optional[str] = None):
    region_name = region or os.getenv("AWS_REGION", "us-east-1")
    print(f"DRUGS: Fetching DB creds from Secrets Manager in region {region_name}...")
    client = boto3.client("secretsmanager", region_name=region_name)
    resp = client.get_secret_value(SecretId=secret_arn)
    data = resp.get("SecretString")
    if not data:
        raise HTTPException(status_code=503, detail="Database credentials unavailable")
    j = json.loads(data)
    return j["username"], j["password"]


def _get_conn():
    host = os.environ["DB_HOST"]
    db_name = os.environ.get("DB_NAME", "drugindex")
    secret_arn = os.environ["DB_SECRET_ARN"]

    username, password = _get_db_creds(secret_arn)
    ctx = ssl.create_default_context()
    print(f"DRUGS: Connecting to Postgres host={host} db={db_name}...")
    return pg_dbapi.connect(user=username, password=password, host=host, database=db_name, ssl_context=ctx)


@router.get("/search")
def search_drugs(
    q: str = Query(..., min_length=2, max_length=128, description="Search text"),
    limit: int = Query(10, ge=1, le=25),
    claims=Depends(get_cognito_user_info),
):
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        conn = _get_conn()
        # Queries: token-AND contains, broad contains, and trigram fuzzy
        contains_sql = (
            "SELECT identifier, brand_name, generic_identifier, license_status "
            "FROM drug_brands WHERE brand_name ILIKE %s ORDER BY similarity(brand_name, %s) DESC LIMIT %s"
        )
        # Escape the literal % operator for DB-API paramstyle using %%
        fuzzy_sql = (
            "SELECT identifier, brand_name, generic_identifier, license_status "
            "FROM drug_brands WHERE brand_name %% %s ORDER BY similarity(brand_name, %s) DESC LIMIT %s"
        )

        cur = conn.cursor()
        try:
            # Lower trigram threshold a bit to tolerate typos
            try:
                cur.execute("SELECT set_limit(%s)", (0.2,))
            except Exception:
                pass

            # 1) Token-AND search if multiple words
            rows_token_and = []
            tokens = [t for t in q.split() if t]
            if len(tokens) >= 2:
                and_clauses = " AND ".join(["brand_name ILIKE %s" for _ in tokens])
                sql = (
                    "SELECT identifier, brand_name, generic_identifier, license_status "
                    f"FROM drug_brands WHERE {and_clauses} "
                    "ORDER BY similarity(brand_name, %s) DESC LIMIT %s"
                )
                params = tuple([f"%{t}%" for t in tokens] + [q, int(limit)])
                print(f"DRUGS: Token-AND search for '{q}' limit={limit}...")
                cur.execute(sql, params)
                rows_token_and = cur.fetchall()
                print(f"DRUGS: Token-AND rows={len(rows_token_and)}")

            # 2) Broad contains search
            print(f"DRUGS: Contains search for '{q}' limit={limit}...")
            cur.execute(contains_sql, (f"%{q}%", q, int(limit)))
            rows_contains = cur.fetchall()
            print(f"DRUGS: Contains rows={len(rows_contains)}")

            # 3) Fuzzy trigram search
            print(f"DRUGS: Fuzzy search for '{q}' limit={limit}...")
            cur.execute(fuzzy_sql, (q, q, int(limit)))
            rows_fuzzy = cur.fetchall()
            print(f"DRUGS: Fuzzy rows={len(rows_fuzzy)}")
        finally:
            try:
                cur.close()
            except Exception:
                pass

        # Merge unique by identifier preserving order: token_and, contains, fuzzy
        seen = set()
        results = []
        merged = []
        for seq in (rows_token_and, rows_contains, rows_fuzzy):
            if isinstance(seq, tuple):
                seq = list(seq)
            try:
                merged.extend(seq)
            except Exception:
                merged += list(seq)
        for r in merged:
            ident = r[0]
            if ident in seen:
                continue
            seen.add(ident)
            results.append({
                "identifier": r[0],
                "brand_name": r[1],
                "generic_identifier": r[2],
                "license_status": r[3],
            })
            if len(results) >= limit:
                break

        return {"items": results}
    except HTTPException:
        raise
    except Exception as e:
        print("DRUGS ERROR:", repr(e))
        traceback.print_exc()
        # Hide internal details
        raise HTTPException(status_code=503, detail="Search temporarily unavailable")
    finally:
        try:
            conn.close()
        except Exception:
            pass


