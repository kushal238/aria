# app/database.py
#
# This module is responsible for initializing the database connection
# and creating table resources. It centralizes all database setup.

import os
import boto3

# --- DynamoDB Configuration ---
USERS_TABLE_NAME = os.getenv("USERS_TABLE_NAME", "Users")
PATIENTS_TABLE_NAME = os.getenv("PATIENTS_TABLE_NAME", "Patients")
DOCTORS_TABLE_NAME = os.getenv("DOCTORS_TABLE_NAME", "Doctors")
PRESCRIPTIONS_TABLE_NAME = os.getenv("PRESCRIPTIONS_TABLE_NAME", "Prescriptions")

dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table(USERS_TABLE_NAME)
patients_table = dynamodb.Table(PATIENTS_TABLE_NAME)
doctors_table = dynamodb.Table(DOCTORS_TABLE_NAME)
prescriptions_table = dynamodb.Table(PRESCRIPTIONS_TABLE_NAME)
