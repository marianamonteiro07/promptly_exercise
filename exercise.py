import sqlite3
import csv
import re
from datetime import datetime
import json
import hashlib

## Function to verify email format before insertion
def check_email(email):
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(pattern, email) is not None

## Function to verify date (ensure no future dates)
def check_date(birthdate):
    try:
        birthdate_as_date = datetime.strptime(birthdate, '%Y-%m-%d').date()
        today = datetime.today().date()
        return birthdate if birthdate_as_date <= today else None
    except Exception:
        return None

## Function to create a unique patient id from patient information,
def create_patient_id(first_name, last_name, birth_date, insurance_number):
    ### Replacing Null values for empty strings so the function doesn't fail
    first_name = first_name if first_name else ""
    last_name = last_name if last_name else ""
    birth_date = birth_date if birth_date else ""
    insurance_number = insurance_number if insurance_number else ""

    concat_patient_info = f"{first_name}{last_name}{birth_date}{insurance_number}"

    return hashlib.md5(concat_patient_info.encode()).hexdigest()

## Function to check duplicate patients based on the insurance number and insert or update the table
def insert_or_update_patient(conn, row):
    cursor = conn.cursor()

    (first_name, last_name, birth_date, gender, address, city, state,
     zip_code, phone, email, emergency_contact_name, emergency_contact_phone,
     blood_type, insurance_provider, insurance_number, marital_status, preferred_language,
     nationality, allergies, last_visit_date) = row

    row = [row_field if row_field and row_field not in ("", "Unknown")
           else None for row_index, row_field in enumerate(row)]

    ## Querying the database to check if the patient already exists
    cursor.execute("SELECT * FROM raw_patient WHERE insurance_number = ?", (insurance_number,))
    patient_from_db = cursor.fetchone()

    ## Updating the values if the patient already exists
    if patient_from_db:
        update_fields = {}
        field_names = ["first_name", "last_name", "birth_date", "gender", "address", "city", "state",
                       "zip_code", "phone_number", "email", "emergency_contact_name",
                       "emergency_contact_phone", "blood_type", "insurance_provider", "insurance_number",
                       "marital_status", "preferred_language", "nationality", "allergies", "last_visit_date"]

        ## Checking the content of each row_field
        for row_index, row_field in enumerate(row):

            ## Checking if there is a value for each column in the new visit of the patient
            ## and if it's not Unknown or None
            if row_field and row_field not in ("Unknown", None):

                ## Attributing the new value for each column in the row and storing in a dict
                update_fields[field_names[row_index]] = row_field

        ## Updating the raw patient table when I find different values in the most recent visit
        if update_fields:
            update_fields["last_visit_date"] = max(patient_from_db[20], last_visit_date)
            update_fields["updated_at"] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            update_query = ", ".join([f"{key} = ?" for key in update_fields.keys()])
            print(update_query)
            values = list(update_fields.values()) + [insurance_number]
            print(values)
            cursor.execute(f"UPDATE raw_patient SET {update_query} WHERE insurance_number = ?", values)

    ## Inserting the patient directly in case I don't find any past entry in the raw patient table
    else:
        print(row)
        cursor.execute('''INSERT INTO raw_patient (first_name, last_name, birth_date, gender,
                            address, city, state, zip_code, phone_number, email, emergency_contact_name, 
                            emergency_contact_phone, blood_type, insurance_provider, insurance_number, 
                            marital_status, preferred_language, nationality, allergies, last_visit_date) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', row)
    conn.commit()

# Database Setup
## Connecting to the database and creating a file
conn = sqlite3.connect("promptly_exercise.db")
cursor = conn.cursor()

# Creating the source table
## Changing id SERIAL PRIMARY KEY to id INTEGER PRIMARY KEY AUTOINCREMENT
## because SERIAL is not a valid data type in sqlite
cursor.execute('''CREATE TABLE IF NOT EXISTS raw_patient (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 first_name VARCHAR(100),
 last_name VARCHAR(100),
 birth_date DATE,
 gender VARCHAR(20),
 address VARCHAR(255),
 city VARCHAR(100),
 state VARCHAR(2),
 zip_code VARCHAR(10),
 phone_number VARCHAR(20),
 email VARCHAR(100),
 emergency_contact_name VARCHAR(200),
 emergency_contact_phone VARCHAR(20),
 blood_type VARCHAR(5),
 insurance_provider VARCHAR(100),
 insurance_number VARCHAR(50),
 marital_status VARCHAR(20),
 preferred_language VARCHAR(50),
 nationality VARCHAR(100),
 allergies TEXT,
 last_visit_date DATE,
 created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
 )''')

# Opening the csv and inserting the data into the raw_patient table
with open("patient.csv", "r") as data:
    reader = csv.reader(data)
    next(reader) # Skipping the header
    for row in reader:
        birth_date, address, email = row[2], row[4], row[9]

        ## Validating birth date
        birth_date = birth_date.strip()
        birth_date = check_date(birth_date) if birth_date else None

        ## Validating the email and replacing it with None if it's invalid
        email = email if check_email(email) else None

        ## Replacing the original values with the transformed ones
        row[2], row[4], row[9] = birth_date, address, email

        ## Inserting the data into the raw_patient table
        insert_or_update_patient(conn, row)

        conn.commit()

# Creating the FHIR patient table
conn.execute('''CREATE TABLE IF NOT EXISTS fhir_patient (
 id VARCHAR(255) PRIMARY KEY,
 full_name VARCHAR(200), 
birth_date DATE,
 gender VARCHAR(20),
 address VARCHAR(255),
 telecom JSONB,
 marital_status VARCHAR(20),
 insurance_number VARCHAR(255),
 nationality VARCHAR(20)
 );''')

# Transforming the raw_patient data to match fhir_patient schema
## Fetching data from raw_patient to insert into fhir_patient
cursor.execute('''SELECT first_name, last_name, birth_date, gender,
                address, phone_number, email, marital_status, insurance_number,
                nationality FROM raw_patient''')

for row in cursor.fetchall():
    ## Keeping the same information from the original table on columns that did not suffer changes
    first_name, last_name, birth_date, gender, address, phone, email, marital_status, insurance_number, nationality = row

    patient_id = create_patient_id(first_name, last_name, birth_date, insurance_number)

    ## Creating full name by combining first and last name values
    full_name = f"{first_name} {last_name}"

    ## Creating JSON for telecom row_field
    telecom = json.dumps({"phone": phone, "email": email})

    ## Inserting the transformed data into the fhir table
    cursor.execute('''INSERT INTO fhir_patient
                    (id, full_name, birth_date, gender, address, telecom, marital_status,
                    insurance_number, nationality) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (patient_id, full_name, birth_date, gender, address,
                    telecom, marital_status, insurance_number, nationality))

conn.commit()
