#!/usr/bin/env python3
"""Query the business_searcher.db directly with SQL or shortcuts."""

import sqlite3
import sys
import json

def query(sql, params=()):
    """Execute SQL query and return results."""
    conn = sqlite3.connect('business_searcher.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql, params)
        
        if sql.strip().upper().startswith('SELECT'):
            rows = cursor.fetchall()
            if not rows:
                print("No results")
                return
            
            # Print headers
            headers = rows[0].keys()
            print(" | ".join(headers))
            print("-" * 80)
            
            # Print rows
            for row in rows:
                values = []
                for i, key in enumerate(headers):
                    val = row[i]
                    if val is None:
                        values.append("NULL")
                    elif isinstance(val, str) and len(val) > 50:
                        values.append(val[:47] + "...")
                    else:
                        values.append(str(val))
                print(" | ".join(values))
            
            print(f"\n({len(rows)} rows)")
        else:
            conn.commit()
            print(f"OK ({cursor.rowcount} rows affected)")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

# Shortcut queries
SHORTCUTS = {
    'latest': """
        SELECT id, title, price, revenue, status, substr(description, 1, 80) as desc_preview
        FROM listings 
        ORDER BY first_seen_at DESC 
        LIMIT 5
    """,
    'all': "SELECT id, source, title, price, status FROM listings ORDER BY first_seen_at DESC LIMIT 20",
    'seek': "SELECT id, title, price, status, substr(description, 1, 60) as desc FROM listings WHERE source='seekbusiness' ORDER BY first_seen_at DESC LIMIT 10",
    'mock': "SELECT id, title, price, revenue, ebitda, status FROM listings WHERE source='mock' LIMIT 10",
    'pass': "SELECT id, title, price, status FROM listings WHERE status='prefilter_pass' LIMIT 10",
    'stats': """
        SELECT 
            source,
            status,
            COUNT(*) as count,
            AVG(price) as avg_price,
            COUNT(description) as with_desc
        FROM listings 
        GROUP BY source, status
    """,
    'schema': ".schema",
    'count': "SELECT COUNT(*) as total FROM listings",
    'tables': "SELECT name FROM sqlite_master WHERE type='table'",
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python db_query.py <SQL|shortcut>")
        print("\nShortcuts:")
        for name in SHORTCUTS:
            print(f"  {name}")
        print("\nExamples:")
        print('  python db_query.py latest')
        print('  python db_query.py "SELECT * FROM listings WHERE price > 500000"')
        print('  python db_query.py "SELECT id, title, json_extract(raw_data, \'$.broker_name\') FROM listings"')
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    # Check if it's a shortcut
    if cmd in SHORTCUTS:
        sql = SHORTCUTS[cmd]
        if sql == ".schema":
            # Special handling for schema
            conn = sqlite3.connect('business_searcher.db')
            cursor = conn.cursor()
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='listings'")
            result = cursor.fetchone()
            if result:
                print(result[0])
            conn.close()
        else:
            query(sql)
    else:
        # Treat as SQL
        query(cmd)
