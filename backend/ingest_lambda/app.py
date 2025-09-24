import os
import ssl
import boto3
import pg8000.native as pg_native

S3_BUCKET = os.environ["S3_BUCKET"]
S3_KEY = os.environ["S3_KEY"]
DB_NAME = os.environ.get("DB_NAME", "drugindex")
DB_HOST = os.environ["DB_HOST"]
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
TMP_PATH = "/tmp/BrandMaster.txt"
SANITIZED_PATH = "/tmp/BrandMaster_sanitized.tsv"

s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager", region_name=REGION)


def _get_db_creds():
    resp = secrets.get_secret_value(SecretId=DB_SECRET_ARN)
    data = resp.get("SecretString")
    if not data:
        raise RuntimeError("DB secret missing SecretString")
    import json
    j = json.loads(data)
    return j["username"], j["password"]


def _connect(username: str, password: str):
    ctx = ssl.create_default_context()
    # Use pg8000 native connection to support COPY with stream
    conn = pg_native.Connection(user=username, password=password, host=DB_HOST, database=DB_NAME, ssl_context=ctx)
    return conn


def _setup_database(conn):
    conn.run("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    conn.run(
        """
        CREATE TABLE IF NOT EXISTS drug_brands (
            identifier BIGINT PRIMARY KEY,
            brand_name TEXT NOT NULL,
            product_identifier BIGINT,
            supplier_identifier BIGINT,
            generic_identifier BIGINT,
            license_number TEXT,
            license_status TEXT,
            excipient TEXT,
            last_updated_on TEXT
        );
        """
    )
    conn.run(
        """
        CREATE INDEX IF NOT EXISTS idx_drug_brands_brand_name_trgm
        ON drug_brands USING gin (brand_name gin_trgm_ops);
        """
    )
    conn.run(
        """
        CREATE TABLE IF NOT EXISTS drug_brands_staging (
            c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT, c5 TEXT,
            c6 TEXT, c7 TEXT, c8 TEXT, c9 TEXT, c10 TEXT
        );
        """
    )
    conn.run("TRUNCATE TABLE drug_brands;")
    conn.run("TRUNCATE TABLE drug_brands_staging;")


def _copy_file(conn):
    # Sanitize: ensure each data row has exactly 10 TSV fields
    expected = 10
    with open(TMP_PATH, "r", encoding="utf-8") as fin, open(SANITIZED_PATH, "w", encoding="utf-8", newline="") as fout:
        header = fin.readline()
        if not header:
            raise RuntimeError("BrandMaster is empty")
        for line in fin:
            line = line.rstrip("\n\r")
            parts = line.split("\t")
            if len(parts) < expected:
                parts += [""] * (expected - len(parts))
            elif len(parts) > expected:
                parts = parts[:expected]
            fout.write("\t".join(parts) + "\n")

    # Load sanitized file into staging (10 columns)
    with open(SANITIZED_PATH, "r", encoding="utf-8") as f:
        conn.run(
            """
            COPY drug_brands_staging FROM STDIN WITH DELIMITER E'\t' NULL ''
            """,
            stream=f,
        )
        # Transform into target table (9 columns), dropping trailing extra column
        conn.run(
            """
            INSERT INTO drug_brands (
                identifier, brand_name, product_identifier, supplier_identifier,
                generic_identifier, license_number, license_status, excipient, last_updated_on
            )
            SELECT
                NULLIF(c1,'')::bigint,
                c2,
                NULLIF(c3,'')::bigint,
                NULLIF(c4,'')::bigint,
                NULLIF(c5,'')::bigint,
                NULLIF(c6,''),
                NULLIF(c7,''),
                NULLIF(c8,''),
                NULLIF(c9,'')
            FROM drug_brands_staging;
            """
        )


def handler(event, context):
    # 1) Download to /tmp
    s3.download_file(S3_BUCKET, S3_KEY, TMP_PATH)

    username, password = _get_db_creds()
    conn = _connect(username, password)
    try:
        _setup_database(conn)
        _copy_file(conn)
        conn.run("COMMIT")

        res = conn.run("SELECT COUNT(*) FROM drug_brands;")
        count = int(res[0][0]) if res and res[0] else 0
        return {"status": "ok", "ingested": count}
    except Exception:
        try:
            conn.run("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass
