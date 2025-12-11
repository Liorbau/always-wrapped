import sqlite3

def check_rihanna():
    conn = sqlite3.connect("my_spotify_data.db")
    cursor = conn.cursor()
    
    print("--- CHECKING FOR RIHANNA ---")
    
    # 1. Search for her specifically
    cursor.execute("SELECT track_name, played_at FROM listening_history WHERE artist_name LIKE '%Rihanna%'")
    results = cursor.fetchall()
    
    if not results:
        print("Result: No Rihanna tracks found in the current database.")
    else:
        print(f"Result: Found {len(results)} tracks:")
        for row in results:
            print(f"- {row[0]} at {row[1]}")

    print("\n--- TOTAL STATS ---")
    cursor.execute("SELECT COUNT(*) FROM listening_history")
    count = cursor.fetchone()[0]
    print(f"Total songs in DB: {count}")

    conn.close()

if __name__ == "__main__":
    check_rihanna()