import mysql.connector
import os

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

cursor = conn.cursor()

def save_rule(user_id, source, destination):
    cursor.execute(
        "INSERT INTO rules (user_id, source_channel, destination_channel) VALUES (%s, %s, %s)",
        (user_id, source, destination)
    )
    conn.commit()

def get_destinations(source):
    cursor.execute(
        "SELECT destination_channel FROM rules WHERE source_channel=%s",
        (source,)
    )
    return [row[0] for row in cursor.fetchall()]
