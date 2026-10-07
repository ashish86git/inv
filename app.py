
import os
import math

import pandas as pd
import psycopg2

from flask import Flask, jsonify, render_template, request
from psycopg2.extras import RealDictCursor, execute_values
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

# Maximum Excel upload size = 20 MB
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

DB_HOST = os.environ.get("DB_HOST", "c89hfa8mgg235.cluster-czrs8kj4isg7.us-east-1.rds.amazonaws.com")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "d2hc5emqstdlu5")
DB_USER = os.environ.get("DB_USER", "u5no93tf65ksha")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "p86edb19173b56140c6f59850879a1341955fa911bfcaf2f17f8ecf207bc42dad")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_SSLMODE = os.environ.get("DB_SSLMODE", "require")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    if DATABASE_URL:

        return psycopg2.connect(
            DATABASE_URL
        )

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        sslmode=DB_SSLMODE
    )


# ============================================================
# JSON CLEANER
# ============================================================

def clean_value(value):

    if value is None:
        return None

    try:

        if pd.isna(value):
            return None

    except Exception:
        pass

    if isinstance(value, float):

        if not math.isfinite(value):
            return None

    if hasattr(value, "item"):

        try:
            return value.item()
        except Exception:
            pass

    if hasattr(value, "strftime"):

        try:
            return value.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except Exception:
            pass

    return value


def clean_record(record):

    return {
        key: clean_value(value)
        for key, value in record.items()
    }


# ============================================================
# DATABASE TABLE
# ============================================================

TABLE_NAME = "inventory_master"


# ============================================================
# CREATE TABLE
# ============================================================

def create_inventory_table():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (

                id BIGSERIAL PRIMARY KEY,

                serial_number TEXT NOT NULL,

                item_number TEXT NOT NULL,

                description TEXT,

                location TEXT,

                um TEXT,

                created_at TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT unique_inventory_serial
                    UNIQUE (serial_number)
            );
            """
        )

        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            idx_inventory_master_item_number
            ON {TABLE_NAME} (item_number);
            """
        )

        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            idx_inventory_master_serial_number
            ON {TABLE_NAME} (serial_number);
            """
        )

        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS
            idx_inventory_master_location
            ON {TABLE_NAME} (location);
            """
        )

        connection.commit()

        print(
            "Inventory Master table checked successfully."
        )

    except Exception as error:

        if connection:
            connection.rollback()

        print(
            "Database table initialization error:",
            error
        )

        raise

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/api/health",
    methods=["GET"]
)
def health():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute("SELECT 1;")

        cursor.fetchone()

        return jsonify({
            "status": "ok",
            "database": "connected"
        })

    except Exception as error:

        print(
            "Health check error:",
            error
        )

        return jsonify({
            "status": "error",
            "database": "disconnected",
            "error": str(error)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# GET MASTER DATA
#
# GET /api/master
#
# Optional:
# /api/master?search=ABC
# ============================================================

@app.route(
    "/api/master",
    methods=["GET"]
)
def get_master():

    connection = None
    cursor = None

    try:

        search = request.args.get(
            "search",
            ""
        ).strip()

        connection = get_db_connection()

        cursor = connection.cursor(
            cursor_factory=RealDictCursor
        )

        if search:

            search_pattern = f"%{search}%"

            cursor.execute(
                f"""
                SELECT
                    id,
                    serial_number,
                    item_number,
                    description,
                    location,
                    um,
                    created_at,
                    updated_at
                FROM {TABLE_NAME}
                WHERE
                    serial_number ILIKE %s
                    OR item_number ILIKE %s
                    OR description ILIKE %s
                    OR location ILIKE %s
                    OR um ILIKE %s
                ORDER BY id DESC;
                """,
                (
                    search_pattern,
                    search_pattern,
                    search_pattern,
                    search_pattern,
                    search_pattern
                )
            )

        else:

            cursor.execute(
                f"""
                SELECT
                    id,
                    serial_number,
                    item_number,
                    description,
                    location,
                    um,
                    created_at,
                    updated_at
                FROM {TABLE_NAME}
                ORDER BY id DESC;
                """
            )

        rows = cursor.fetchall()

        records = [
            clean_record(dict(row))
            for row in rows
        ]

        return jsonify(records)

    except Exception as error:

        print(
            "Get master data error:",
            error
        )

        return jsonify({
            "error": str(error)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# PRINT ALL
#
# IMPORTANT:
# This endpoint is specifically used by:
#
# fetch("/api/master/print-all")
#
# It only READS database data.
# It does NOT modify/delete/update anything.
# ============================================================

@app.route(
    "/api/master/print-all",
    methods=["GET"]
)
def print_all_records():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            cursor_factory=RealDictCursor
        )

        cursor.execute(
            f"""
            SELECT
                id,
                serial_number,
                item_number,
                description,
                location,
                um,
                created_at,
                updated_at
            FROM {TABLE_NAME}
            ORDER BY id ASC;
            """
        )

        rows = cursor.fetchall()

        records = [
            clean_record(dict(row))
            for row in rows
        ]

        return jsonify(records)

    except Exception as error:

        print(
            "Print all records error:",
            error
        )

        return jsonify({
            "error": str(error)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# ALL DATA ALIAS
#
# Optional compatibility endpoint.
#
# GET /api/master/all
# ============================================================

@app.route(
    "/api/master/all",
    methods=["GET"]
)
def get_all_master_records():

    return print_all_records()


# ============================================================
# GET SINGLE RECORD
#
# GET /api/master/<id>
# ============================================================

@app.route(
    "/api/master/<int:record_id>",
    methods=["GET"]
)
def get_single_master_record(
    record_id
):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor(
            cursor_factory=RealDictCursor
        )

        cursor.execute(
            f"""
            SELECT
                id,
                serial_number,
                item_number,
                description,
                location,
                um,
                created_at,
                updated_at
            FROM {TABLE_NAME}
            WHERE id = %s;
            """,
            (record_id,)
        )

        row = cursor.fetchone()

        if not row:

            return jsonify({
                "error": "Inventory record not found."
            }), 404

        record = clean_record(
            dict(row)
        )

        return jsonify(record)

    except Exception as error:

        print(
            "Get single record error:",
            error
        )

        return jsonify({
            "error": str(error)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# BULK SELECTED
#
# GET:
# /api/master/bulk-selected?ids=1,2,3
# ============================================================

@app.route(
    "/api/master/bulk-selected",
    methods=["GET"]
)
def get_bulk_selected():

    connection = None
    cursor = None

    try:

        ids_parameter = request.args.get(
            "ids",
            ""
        ).strip()

        if not ids_parameter:

            return jsonify({
                "error": "No record IDs were provided."
            }), 400

        raw_ids = ids_parameter.split(",")

        record_ids = []

        for value in raw_ids:

            value = value.strip()

            if not value:
                continue

            try:

                record_id = int(value)

            except ValueError:

                return jsonify({
                    "error":
                        f"Invalid record ID: {value}"
                }), 400

            if record_id > 0:
                record_ids.append(record_id)

        record_ids = list(
            dict.fromkeys(record_ids)
        )

        if not record_ids:

            return jsonify({
                "error": "No valid record IDs were provided."
            }), 400

        connection = get_db_connection()

        cursor = connection.cursor(
            cursor_factory=RealDictCursor
        )

        cursor.execute(
            f"""
            SELECT
                id,
                serial_number,
                item_number,
                description,
                location,
                um,
                created_at,
                updated_at
            FROM {TABLE_NAME}
            WHERE id = ANY(%s)
            ORDER BY id ASC;
            """,
            (record_ids,)
        )

        rows = cursor.fetchall()

        records = [
            clean_record(dict(row))
            for row in rows
        ]

        return jsonify(records)

    except Exception as error:

        print(
            "Bulk selected records error:",
            error
        )

        return jsonify({
            "error": str(error)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# UPLOAD EXCEL
#
# POST /api/upload-master
#
# Excel required columns:
#
# Serial Number
# Item Number
# Description
# Location
# UM
#
# Existing Serial Number:
# UPDATE
#
# New Serial Number:
# INSERT
# ============================================================

@app.route(
    "/api/upload-master",
    methods=["POST"]
)
def upload_master():

    connection = None
    cursor = None

    try:

        if "file" not in request.files:

            return jsonify({
                "error": "No Excel file was provided."
            }), 400

        file = request.files["file"]

        if not file:

            return jsonify({
                "error": "Invalid Excel file."
            }), 400

        if not file.filename:

            return jsonify({
                "error": "Please select an Excel file."
            }), 400

        filename = file.filename.lower()

        if not (
            filename.endswith(".xlsx")
            or filename.endswith(".xls")
        ):

            return jsonify({
                "error":
                    "Only .xlsx and .xls Excel files are allowed."
            }), 400


        # ----------------------------------------------------
        # READ EXCEL
        # ----------------------------------------------------

        try:

            excel_df = pd.read_excel(
                file
            )

        except Exception as error:

            return jsonify({
                "error":
                    f"Unable to read Excel file: {error}"
            }), 400


        # ----------------------------------------------------
        # REQUIRED COLUMNS
        # ----------------------------------------------------

        required_columns = [
            "Serial Number",
            "Item Number",
            "Description",
            "Location",
            "UM"
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in excel_df.columns
        ]

        if missing_columns:

            return jsonify({
                "error":
                    "Missing required Excel columns.",
                "missing_columns":
                    missing_columns,
                "required_columns":
                    required_columns
            }), 400


        # ----------------------------------------------------
        # KEEP REQUIRED COLUMNS ONLY
        # ----------------------------------------------------

        df = excel_df[
            required_columns
        ].copy()


        # ----------------------------------------------------
        # CLEAN VALUES
        # ----------------------------------------------------

        for column in required_columns:

            df[column] = (
                df[column]
                .apply(
                    lambda value:
                        None
                        if pd.isna(value)
                        else str(value).strip()
                )
            )


        # ----------------------------------------------------
        # REMOVE EMPTY SERIAL NUMBERS
        # ----------------------------------------------------

        df = df[
            df["Serial Number"].notna()
            & (
                df["Serial Number"]
                .astype(str)
                .str.strip()
                != ""
            )
        ].copy()


        total = len(excel_df)


        # ----------------------------------------------------
        # REMOVE DUPLICATE SERIAL NUMBERS
        #
        # If same serial appears multiple times,
        # last row wins.
        # ----------------------------------------------------

        df = df.drop_duplicates(
            subset=["Serial Number"],
            keep="last"
        )


        rows_processed = len(df)


        if rows_processed == 0:

            return jsonify({
                "message":
                    "No valid inventory records found in Excel.",
                "total": total,
                "rows_processed": 0,
                "inserted": 0,
                "updated": 0
            })


        # ----------------------------------------------------
        # PREPARE VALUES
        # ----------------------------------------------------

        values = []

        for _, row in df.iterrows():

            serial_number = (
                None
                if row["Serial Number"] is None
                else str(
                    row["Serial Number"]
                ).strip()
            )

            item_number = (
                None
                if row["Item Number"] is None
                else str(
                    row["Item Number"]
                ).strip()
            )

            description = (
                None
                if row["Description"] is None
                else str(
                    row["Description"]
                ).strip()
            )

            location = (
                None
                if row["Location"] is None
                else str(
                    row["Location"]
                ).strip()
            )

            um = (
                None
                if row["UM"] is None
                else str(
                    row["UM"]
                ).strip()
            )

            if not serial_number:

                continue

            if not item_number:

                item_number = ""

            values.append(
                (
                    serial_number,
                    item_number,
                    description,
                    location,
                    um
                )
            )


        if not values:

            return jsonify({
                "message":
                    "No valid inventory records found.",
                "total": total,
                "rows_processed": 0,
                "inserted": 0,
                "updated": 0
            })


        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        connection = get_db_connection()

        cursor = connection.cursor()


        # ----------------------------------------------------
        # FIND EXISTING SERIAL NUMBERS
        # ----------------------------------------------------

        serial_numbers = [
            row[0]
            for row in values
        ]

        cursor.execute(
            f"""
            SELECT serial_number
            FROM {TABLE_NAME}
            WHERE serial_number = ANY(%s);
            """,
            (serial_numbers,)
        )

        existing_serials = {
            row[0]
            for row in cursor.fetchall()
        }


        # ----------------------------------------------------
        # COUNT INSERT / UPDATE
        # ----------------------------------------------------

        updated_count = sum(
            1
            for serial in serial_numbers
            if serial in existing_serials
        )

        inserted_count = sum(
            1
            for serial in serial_numbers
            if serial not in existing_serials
        )


        # ----------------------------------------------------
        # UPSERT
        #
        # Existing serial_number -> UPDATE
        # New serial_number      -> INSERT
        # ----------------------------------------------------

        execute_values(
            cursor,
            f"""
            INSERT INTO {TABLE_NAME}
            (
                serial_number,
                item_number,
                description,
                location,
                um
            )
            VALUES %s

            ON CONFLICT (serial_number)
            DO UPDATE SET

                item_number = EXCLUDED.item_number,

                description = EXCLUDED.description,

                location = EXCLUDED.location,

                um = EXCLUDED.um,

                updated_at = CURRENT_TIMESTAMP;
            """,
            values
        )


        connection.commit()


        return jsonify({
            "message":
                "Excel uploaded and inventory master updated successfully.",
            "total": total,
            "rows_processed": len(values),
            "inserted": inserted_count,
            "updated": updated_count
        })


    except Exception as error:

        if connection:

            connection.rollback()

        print(
            "Excel upload error:",
            error
        )

        return jsonify({
            "error":
                f"Excel upload failed: {error}"
        }), 500


    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# DELETE SINGLE RECORD
#
# DELETE /api/master/<id>
# ============================================================

@app.route(
    "/api/master/<int:record_id>",
    methods=["DELETE"]
)
def delete_single_record(
    record_id
):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            f"""
            DELETE FROM {TABLE_NAME}
            WHERE id = %s
            RETURNING id;
            """,
            (record_id,)
        )

        deleted = cursor.fetchone()

        if not deleted:

            connection.rollback()

            return jsonify({
                "error":
                    "Inventory record not found."
            }), 404

        connection.commit()

        return jsonify({
            "message":
                "Inventory record deleted successfully.",
            "id":
                deleted[0]
        })

    except Exception as error:

        if connection:
            connection.rollback()

        print(
            "Delete single record error:",
            error
        )

        return jsonify({
            "error": str(error)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# DELETE ALL RECORDS
#
# DELETE /api/master?confirm=yes
# ============================================================

@app.route(
    "/api/master",
    methods=["DELETE"]
)
def delete_all_records():

    connection = None
    cursor = None

    try:

        confirm = request.args.get(
            "confirm",
            ""
        ).lower()

        if confirm != "yes":

            return jsonify({
                "error":
                    "Delete All requires confirm=yes."
            }), 400

        connection = get_db_connection()

        cursor = connection.cursor()

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {TABLE_NAME};
            """
        )

        count_before = cursor.fetchone()[0]

        cursor.execute(
            f"""
            DELETE FROM {TABLE_NAME};
            """
        )

        connection.commit()

        return jsonify({
            "message":
                f"All inventory records deleted successfully. {count_before} records deleted.",
            "deleted":
                count_before
        })

    except Exception as error:

        if connection:
            connection.rollback()

        print(
            "Delete all records error:",
            error
        )

        return jsonify({
            "error": str(error)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def request_entity_too_large(error):

    return jsonify({
        "error":
            "File is too large. Maximum allowed size is 20 MB."
    }), 413


# ============================================================
# GENERAL ERROR
# ============================================================

@app.errorhandler(500)
def internal_server_error(error):

    return jsonify({
        "error":
            "Internal server error."
    }), 500


# ============================================================
# STARTUP
# ============================================================

if __name__ == "__main__":

    print("")
    print("====================================================")
    print(" INVENTORY MASTER - FLASK APPLICATION")
    print("====================================================")

    print(
        "App file:",
        os.path.abspath(__file__)
    )

    print(
        "Template folder:",
        os.path.abspath(app.template_folder)
    )

    print(
        "Index template:",
        os.path.abspath(
            os.path.join(
                app.template_folder,
                "index.html"
            )
        )
    )

    print(
        "Index exists:",
        os.path.exists(
            os.path.join(
                app.template_folder,
                "index.html"
            )
        )
    )

    print(
        "Database:",
        DB_NAME
    )

    print(
        "Database host:",
        DB_HOST
    )

    print(
        "Table:",
        TABLE_NAME
    )

    print("====================================================")

    # Create/check database table
    create_inventory_table()

    # Start Flask
    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "5000"
            )
        ),
        debug=True
    )

