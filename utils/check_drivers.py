import pyodbc

print("--- Scanning for Installed SQL Server Drivers ---\n")

drivers = [d for d in pyodbc.drivers() if 'SQL' in d]

if drivers:
    print(f"✅ Found {len(drivers)} SQL drivers:")
    for driver in drivers:
        print(f"   • {driver}")
    
    print("\nRecommended Action:")
    print(f"Copy the name of the newest driver and update 'db_manager.py'")
    print(f"Example: DRIVER={{{drivers[0]}}};")
else:
    print("❌ No SQL Server drivers found!")
    print("You need to download the 'ODBC Driver for SQL Server' from Microsoft.")