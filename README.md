#  Patient Data Pipeline

## Goal

The goal of this exercise was to set up a local database, ingest a provided patient CSV file into the database and transform the data into a standardized FHIR Patient table.

## Pre-requisites

To run this script, you will need the following libraries, which are all native to Python: 
- sqlite3
- csv
- re
- datetime
- json
- hashlib

This script was created using Python 3.8.

## How to run

To execute this script, first ensure you meet all above-mentioned pre-requisites. After this, run the following command: 

```
python3 exercise.py
```

Please note that, in order to re-run, you will need to drop the created tables using the following commands:

```
import sqlite3
conn = sqlite3.connect("promptly_exercise.db")
cursor = conn.cursor()
cursor.execute("drop table raw_patient")
cursor.execute("drop table fhir_patient")
conn.commit()
```

Alternatively, you can simply delete the created database (promptly_exercise.db) and re-run the initial commmand.

## Overview

The script is comprised of 3 steps: 

1) Creating the database:
    - To achieve this step, I used SQLite, mainly due to its minimal required setup and the provided dataset's small size.
2) Creating the raw_patient table and inserting the csv data into it:
    - Before inserting the data into the table, several verifications were made, namely:
      - Verify if the columns had missing values. When this happened, I inserted a Null value instead. In cases where the columns had "Unknown" values, these were also changed to Null. This solution was chosen due to two reasons -consistency and compliance with the database schema. In one specific case, in the column "blood_type", the data type was VARCHAR(5) and the csv had "Unknown" values, surpassing the character limit.
      - Validate the email format. To achieve this, I used regular expressions to check if 1) the local part of the email has letters, both upper and lower case, numbers, special characters _.+- and has one or more characters; 2) after this string is the @ symbol; 3) the domain name has letters, both upper and lower case, numbers and hyphens; 4) after the domain there is a dot; 5) after the domain there is a top-level domain with letters, numbers, dots or hyphens and there is one or more characters. If the email was not valid, I changed it to Null, as to avoid the patient being contacted through a non-existing channel.
      - Validate birth date. Here I verified if the date was valid by checking if it's not a future date.
    - While inserting data into the table, one verification was made, namely:
      - Check if there are duplicate patient entries to only keep the most recent data on the table. This was done using the "insurance_number" column: if two patients have the same insurance number, I checked the "last_visit_date" column to see which information is most up-to-date. If the most recent entry has different data, I update the table to replace the older information. The column "updated_at" is also changed to the timestamp of the update operation.
3) Creating the fhir_patient table and inserting transformed raw_patient data into it:
    - Before inserting the data into the table, several transformations were made, namely:
      - Generating a unique patient ID from patient attributes. To achieve this, i used MD5 hashing, because 1) it always creates a hash with the same size (32 characters) and 2) always generates the same output given the same input, allowing reproducibility. The attributes used to create the hash were "first_name", "last_name" (less likely to not be filled), "birth_date" and "insurance_number". The latter was used to guarantee uniqueness. Before creating the hash, Nulls were replaced by empty strings.  
      - Creating a "full_name" column. This was achieved by concatenating "first_name" and "last_name". 
      - Creating a "telecom" column which consisted in a JSON object with two fields, phone and email. To do this i used the "json" library, converting the "email" and "phone" columns into a JSON string.
  
