import asyncio
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path

async def fix_user_data_types():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_file = Path(__file__).parent.parent / "core" / "credentials.json"
    creds = ServiceAccountCredentials.from_json_keyfile_name(str(creds_file), scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("Ilm Ul Quran")
    ws = spreadsheet.worksheet("users")
    headers = ws.row_values(1)
    # columns to convert to string
    convert_cols = ['mobile', 'cnic', 'verification_pin']
    for col_name in convert_cols:
        if col_name not in headers:
            continue
        col_idx = headers.index(col_name) + 1
        data = ws.col_values(col_idx)[1:]  # skip header
        for row_num, value in enumerate(data, start=2):
            if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
                ws.update_cell(row_num, col_idx, str(value))
                print(f"Fixed row {row_num}, column {col_name}: {value} -> {str(value)}")
    print("Data type conversion completed.")

if __name__ == "__main__":
    asyncio.run(fix_user_data_types())