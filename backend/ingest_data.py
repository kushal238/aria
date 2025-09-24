import os
import json
import boto3
import psycopg2

# --- CONFIGURATION ---
# Environment overrides are supported; defaults below include placeholders.
# Update the placeholders or set the environment variables before running.

# AWS region for Secrets Manager client
REGION = os.getenv("INGEST_REGION", "us-east-1")  # needs to be changed for me if your region is not us-east-1

# Full ARN of the DB credentials secret created by the aria stack
SECRET_ARN = os.getenv("INGEST_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:879594333319:secret:aria-db-credentials-PaLxb4")  # needs to be changed for me

# Aurora writer endpoint (NOT the -ro reader endpoint)
DB_HOST = os.getenv("INGEST_DB_HOST", "aria-drug-database.cluster-c2fy4ikogv67.us-east-1.rds.amazonaws.com")  # needs to be changed for me

# Database name created by CloudFormation (usually 'drugindex' unless changed)
DB_NAME = os.getenv("INGEST_DB_NAME", "drugindex")  # typically unchanged

# Path to CDCI BrandMaster.txt (tab-separated)
BRAND_MASTER_FILE = os.getenv(
    "INGEST_BRAND_MASTER_FILE",
    "../CommonDrugCodesForIndia_FlatFilePackage/BrandMaster.txt",
)  # needs to be changed for me if your file moved


def get_database_credentials(region: str, secret_arn: str) -> tuple[str, str]:
    """Fetch master username/password from AWS Secrets Manager."""
    print("Fetching database credentials from Secrets Manager...")
    try:
        client = boto3.client("secretsmanager", region_name=region)
        resp = client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(resp["SecretString"])
        username = secret["username"]
        password = secret["password"]
        print("Successfully fetched credentials.")
        return username, password
    except Exception as exc:
        print(f"Error fetching credentials: {exc}")
        raise


def setup_database(conn: psycopg2.extensions.connection) -> None:
    """
    Create extension, table and indexes. Idempotent and re-runnable safely.
    - Table stores all BrandMaster.txt columns.
    - last_updated_on kept as TEXT to avoid parsing issues on ingest.
    """
    print("Setting up database schema...")
    with conn.cursor() as cur:
        print("Creating pg_trgm extension (if not exists)...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

        print("Creating table drug_brands (if not exists)...")
        cur.execute(
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

        print("Creating GIN trigram index on brand_name (if not exists)...")
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_drug_brands_brand_name_trgm
            ON drug_brands
            USING gin (brand_name gin_trgm_ops);
            """
        )

        print("Truncating existing data in drug_brands...")
        cur.execute("TRUNCATE TABLE drug_brands;")

    conn.commit()
    print("Database schema setup complete.")


def ingest_data(conn: psycopg2.extensions.connection, brand_master_path: str) -> int:
    """Bulk-ingest BrandMaster.txt via PostgreSQL COPY for speed."""
    print(f"Starting data ingestion from {brand_master_path}...")
    with conn.cursor() as cur:
        with open(brand_master_path, "r", encoding="utf-8") as f:
            # Skip header line
            header = next(f, None)
            if header is None:
                raise RuntimeError("BrandMaster file is empty.")

            copy_sql = (
                """
                COPY drug_brands (
                    identifier,
                    brand_name,
                    product_identifier,
                    supplier_identifier,
                    generic_identifier,
                    license_number,
                    license_status,
                    excipient,
                    last_updated_on
                ) FROM STDIN WITH (FORMAT csv, DELIMITER E'\t')
                """
            )
            cur.copy_expert(copy_sql, f)

    conn.commit()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM drug_brands;")
        count = cur.fetchone()[0]
    print(f"Successfully ingested {count} records into drug_brands.")
    return count


def main() -> None:
    # Basic validation of required config
    missing: list[str] = []
    if not SECRET_ARN or SECRET_ARN.startswith("REPLACE_WITH_"):
        missing.append("SECRET_ARN")
    if not DB_HOST or DB_HOST.startswith("REPLACE_WITH_"):
        missing.append("DB_HOST")
    if not os.path.exists(BRAND_MASTER_FILE):
        print(f"Error: Data file not found at {BRAND_MASTER_FILE}")
        return
    if missing:
        print("Error: Please set the following before running:")
        for key in missing:
            print(f" - {key}  # needs to be changed for me")
        print("Alternatively, export INGEST_SECRET_ARN / INGEST_DB_HOST / INGEST_REGION / INGEST_BRAND_MASTER_FILE env vars.")
        return

    try:
        username, password = get_database_credentials(REGION, SECRET_ARN)
        print(f"Connecting to database at {DB_HOST} (db={DB_NAME})...")
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=username,
            password=password,
            sslmode="require"  # enforce TLS in transit
        )
        try:
            setup_database(conn)
            ingest_data(conn, BRAND_MASTER_FILE)
            print("\nBackfill completed successfully.")
        finally:
            conn.close()
            print("Database connection closed.")
    except Exception as exc:
        print(f"Ingestion failed: {exc}")


if __name__ == "__main__":
    main()
